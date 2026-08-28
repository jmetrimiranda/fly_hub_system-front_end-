"""Configuração operacional que o operador muda pela interface.

Chave-valor, e não uma coluna por opção, porque estes valores não têm relação
entre si nem com nenhuma entidade do domínio — cada um é uma escolha isolada de
quem opera. Uma tabela nova por opção seria uma migration por botão.

Distinto de `core/config.py`: lá está o que o **ambiente** define (endereços,
credenciais, limites), lido uma vez no start e imutável em execução. Aqui está
o que a **pessoa** decide com a aplicação no ar, e que precisa sobreviver a um
reinício — desligar a inferência de propósito não pode ser desfeito por um
`docker compose restart`.
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    """Sempre texto. Quem lê converte — ver `services/app_settings_service.py`."""
