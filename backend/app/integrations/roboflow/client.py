"""Cliente HTTP do Roboflow.

O parâmetro que importa
-----------------------
Cada imagem sobe com `split=` explícito. Sem ele o Roboflow reparticiona por
conta própria — e o split dele é aleatório, o que desfaz inteiro o trabalho da
divisão temporal: quadros vizinhos no tempo voltariam a cair em partições
diferentes e o vazamento de treino na validação estaria de volta, agora
invisível porque aconteceu do outro lado da rede.

`batch` e `tag` levam a versão do dataset. Meses depois, quando alguém
perguntar de qual voo veio determinada imagem, é a única resposta possível.

Por que HTTP e não o SDK
------------------------
O pacote `roboflow` é síncrono e imprime na saída padrão; o M4TD precisava de
uma thread e de `redirect_stdout` só por causa dele. Falando o mesmo endereço
por `httpx.AsyncClient`, o envio é I/O aguardável e cabe numa tarefa do próprio
laço de eventos, sem thread e sem capturar saída de terceiro.

A chave
-------
Chega por parâmetro, viaja na query string da requisição — que é o que a API do
Roboflow exige — e nunca é registrada. As mensagens de erro deste módulo citam
o arquivo e o código HTTP, jamais a URL montada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.errors import RoboflowError, RoboflowNotConfiguredError
from app.core.logging import get_logger

log = get_logger(__name__)

DEFAULT_TAG = "drone"

# A chave viaja na query string porque a API do Roboflow exige assim. Toda
# mensagem que possa ter tocado uma URL passa por aqui antes de ser gravada ou
# devolvida — biblioteca nenhuma promete não ecoar a URL numa exceção.
_API_KEY_IN_URL = re.compile(r"(api_key=)[^&\s\"\']+")


def scrub(text: str) -> str:
    """Troca `api_key=...` por `api_key=***`. Idempotente e barato."""
    return _API_KEY_IN_URL.sub(r"\1***", text)


@dataclass(frozen=True, slots=True)
class RoboflowTarget:
    """Para onde enviar. `api_key` nunca sai daqui — nem em `repr`."""

    workspace: str
    project: str
    api_key: str

    def __repr__(self) -> str:  # pragma: no cover — proteção contra traceback
        return f"RoboflowTarget(workspace={self.workspace!r}, project={self.project!r})"


class RoboflowClient:
    def __init__(self, target: RoboflowTarget | None = None, timeout: float = 30.0) -> None:
        self._target = target or self._from_settings()
        self._timeout = timeout
        self._base = settings.roboflow_api_url.rstrip("/")

    @staticmethod
    def _from_settings() -> RoboflowTarget:
        """Credencial do ambiente. É o caminho de quem não cadastrou nenhuma."""
        if not settings.roboflow_configured:
            raise RoboflowNotConfiguredError()
        return RoboflowTarget(
            workspace=settings.roboflow_workspace,
            project=settings.roboflow_project,
            api_key=settings.roboflow_api_key,
        )

    @property
    def workspace(self) -> str:
        return self._target.workspace

    @property
    def project(self) -> str:
        return self._target.project

    @property
    def _upload_url(self) -> str:
        return f"{self._base}/dataset/{self._target.project}/upload"

    async def upload_image(
        self,
        client: httpx.AsyncClient,
        path: Path,
        split: str,
        batch: str,
        tags: list[str],
    ) -> str:
        """Sobe um frame. Devolve o id atribuído pelo Roboflow.

        O `AsyncClient` vem de fora: um lote de 500 imagens abre uma conexão só
        e reaproveita, em vez de refazer o handshake TLS quinhentas vezes.
        """
        params: list[tuple[str, str]] = [
            ("api_key", self._target.api_key),
            ("split", split),
            ("batch", batch),
        ]
        params.extend(("tag", tag) for tag in tags)

        try:
            with path.open("rb") as handle:
                response = await client.post(
                    self._upload_url,
                    params=params,
                    files={"file": (path.name, handle, "image/jpeg")},
                    timeout=self._timeout,
                )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            # Só o código HTTP: o texto do erro pode ecoar a URL, e a URL leva
            # a chave.
            raise RoboflowError(
                f"O Roboflow recusou {path.name} (HTTP {exc.response.status_code}).",
                filename=path.name,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RoboflowError(
                f"Falha de rede ao enviar {path.name} para o Roboflow: "
                f"{scrub(str(exc))[:120]}",
                filename=path.name,
            ) from exc

        if isinstance(body, dict) and body.get("error"):
            raise RoboflowError(f"O Roboflow recusou {path.name}.", filename=path.name)
        return str((body or {}).get("id", ""))
