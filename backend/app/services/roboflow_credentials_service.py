"""Credenciais do Roboflow: gravar, listar, apagar.

O pedido era simples — poder gravar a chave e, no acesso seguinte, escolher
numa lista suspensa. O que isso implica não é simples, e as regras abaixo não
têm exceção:

* A chave é **cifrada em repouso**, com `Fernet` e uma chave derivada de
  `SECRET_KEY`. Nunca em texto claro no banco.
* Nenhum endpoint devolve a chave. Nem inteira, nem os últimos quatro
  caracteres: chave mascarada continua sendo vazamento parcial, e a máscara só
  ajuda quem já tem o resto.
* A chave não entra em log, nem em mensagem de erro, nem em `repr` de schema.
* Sem `SECRET_KEY` definida, gravar é **recusado** e o motivo aparece na tela.
  Inventar uma chave padrão produziria um banco que não abre no reinício
  seguinte e uma falsa sensação de segredo.

O texto claro existe em memória por dois instantes: quando a credencial é
gravada e quando um upload a decifra para montar a requisição.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, SecretKeyMissingError
from app.core.logging import get_logger
from app.integrations.roboflow.client import RoboflowTarget
from app.models.dataset import RoboflowCredential
from app.schemas.dataset import RoboflowCredentialCreate, RoboflowCredentialOut

log = get_logger(__name__)


class RoboflowCredentialService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[RoboflowCredentialOut]:
        """Lista **sem** a chave. Não existe variante deste método que a traga."""
        rows = (
            await self._session.execute(
                select(RoboflowCredential).order_by(RoboflowCredential.created_at.desc())
            )
        ).scalars().all()
        return [RoboflowCredentialOut.model_validate(row) for row in rows]

    async def create(self, payload: RoboflowCredentialCreate) -> RoboflowCredentialOut:
        from app.core.crypto import encrypt

        if not settings.secret_configured:
            raise SecretKeyMissingError()

        exists = await self._session.scalar(
            select(RoboflowCredential).where(RoboflowCredential.label == payload.label)
        )
        if exists is not None:
            raise ConflictError(f"Já existe uma credencial chamada “{payload.label}”.")

        credential = RoboflowCredential(
            label=payload.label,
            workspace=payload.workspace,
            project=payload.project,
            api_key_encrypted=encrypt(payload.api_key),
        )
        self._session.add(credential)
        await self._session.commit()
        await self._session.refresh(credential)
        # O log registra o rótulo e o destino. Nunca a chave.
        log.info(
            "roboflow_credential_saved",
            credential_id=credential.id,
            label=credential.label,
            workspace=credential.workspace,
        )
        return RoboflowCredentialOut.model_validate(credential)

    async def delete(self, credential_id: int) -> None:
        credential = await self._session.get(RoboflowCredential, credential_id)
        if credential is None:
            raise NotFoundError(f"Credencial {credential_id} não encontrada.")
        await self._session.delete(credential)
        await self._session.commit()
        log.info("roboflow_credential_deleted", credential_id=credential_id)

    async def target(self, credential_id: int) -> RoboflowTarget:
        """Decifra para uso imediato. O único lugar que devolve texto claro."""
        from app.core.crypto import decrypt

        credential = await self._session.get(RoboflowCredential, credential_id)
        if credential is None:
            raise NotFoundError(f"Credencial {credential_id} não encontrada.")
        credential.last_used_at = datetime.now(UTC)
        await self._session.commit()
        return RoboflowTarget(
            workspace=credential.workspace,
            project=credential.project,
            api_key=decrypt(credential.api_key_encrypted),
        )
