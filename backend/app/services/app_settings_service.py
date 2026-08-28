"""Leitura e escrita das opções que o operador muda pela interface.

Texto no banco, tipo em Python. A tabela guarda tudo como string porque a
alternativa — uma coluna por tipo, ou JSON — resolveria um problema que não
existe: são meia dúzia de chaves e cada leitor sabe o que espera encontrar.

Nada aqui tem cache em memória. Uma cópia local seria mais rápida e passaria a
divergir no dia em que outro processo escrevesse a mesma chave; o custo de um
SELECT por chave, uma vez por clique, não paga esse risco.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.settings import AppSetting

log = get_logger(__name__)

TRUE_VALUES = {"1", "true", "yes", "on"}

#: Inferência ligada. Ver `services/model_service.py`.
MODEL_INFERENCE_ENABLED = "model.inference_enabled"


class AppSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> str | None:
        return await self._session.scalar(select(AppSetting.value).where(AppSetting.key == key))

    async def get_bool(self, key: str, default: bool) -> bool:
        """`default` vale para chave nunca escrita — não para valor inválido.

        Lixo gravado na coluna cai no `default` também, mas com aviso no log:
        silenciar seria decidir por quem opera sem dizer nada.
        """
        raw = await self.get(key)
        if raw is None:
            return default
        normalized = raw.strip().lower()
        if normalized in TRUE_VALUES:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        log.warning("app_setting_invalida", key=key, value=raw, usando=default)
        return default

    async def set(self, key: str, value: str) -> None:
        """Insere ou atualiza. Sem `ON CONFLICT`: o SQLite dos testes não o tem
        na mesma forma que o Postgres, e são duas linhas de Python."""
        row = await self._session.get(AppSetting, key)
        if row is None:
            self._session.add(AppSetting(key=key, value=value))
        else:
            row.value = value
        await self._session.commit()

    async def set_bool(self, key: str, value: bool) -> None:
        await self.set(key, "true" if value else "false")
