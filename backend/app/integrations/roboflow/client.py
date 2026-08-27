"""Cliente HTTP do Roboflow.

Envia as imagens já particionadas pelo backend. O split vem pronto — o
Roboflow recebe `split=train|valid|test` e respeita a divisão temporal em vez
de refazer a sua própria.
"""

from pathlib import Path

import httpx

from app.core.config import settings
from app.core.errors import RoboflowError, RoboflowNotConfiguredError
from app.core.logging import get_logger

log = get_logger(__name__)


class RoboflowClient:
    def __init__(self, timeout: float = 30.0) -> None:
        if not settings.roboflow_configured:
            raise RoboflowNotConfiguredError()
        self._timeout = timeout
        self._base = settings.roboflow_api_url.rstrip("/")
        self._dataset_url = (
            f"{self._base}/dataset/{settings.roboflow_project}/upload"
            f"?api_key={settings.roboflow_api_key}"
        )

    async def upload_image(self, path: Path, split: str, batch: str) -> str:
        """Sobe um frame. Devolve o id atribuído pelo Roboflow."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                with path.open("rb") as handle:
                    response = await client.post(
                        self._dataset_url,
                        files={"file": (path.name, handle, "image/jpeg")},
                        data={"split": split, "batch": batch},
                    )
                response.raise_for_status()
                return str(response.json().get("id", ""))
        except httpx.HTTPError as exc:
            log.warning("roboflow_upload_failed", file=path.name, error=str(exc))
            raise RoboflowError(
                f"Falha ao enviar {path.name} para o Roboflow.", filename=path.name
            ) from exc
