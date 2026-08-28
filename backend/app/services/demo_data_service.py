"""Remoção dos dados de demonstração.

O `seed.py` existe para que a aplicação recém-clonada abra com conteúdo — uma
tela vazia parece quebrada, e quem nunca viu o sistema não sabe distinguir uma
coisa da outra. Assim que voos de verdade entram, porém, as duas fontes se
misturam na mesma tabela e ninguém sabe mais o que é o quê.

A regra mora aqui, e não no `seed.py`, porque tem dois consumidores: o comando
`python -m app.db.seed --clear` e o `DELETE /api/v1/admin/seed` que a tela
Datasets aciona. Duas cópias divergiriam, e a que divergisse apagaria demais.

O que **não** se faz aqui: apagar por data, por faixa de id ou por padrão de
nome. Qualquer heurística desse tipo acerta hoje e erra no dia em que uma
coleta real cair no meio. A marca `source` é explícita justamente para não
precisar adivinhar.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.dataset import Dataset, DatasetImage
from app.models.enums import DataSource
from app.models.inspection import Damage, Inspection, ModelMetric, SapNote

log = get_logger(__name__)


class DemoDataSummary(BaseModel):
    """Quanto há (ou quanto foi removido) de cada coisa."""

    datasets: int = 0
    inspections: int = 0
    model_metrics: int = 0
    sap_notes: int = 0

    @property
    def total(self) -> int:
        return self.datasets + self.inspections + self.model_metrics + self.sap_notes


class DemoDataService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def summary(self) -> DemoDataSummary:
        """Quanto de demonstração ainda existe. O modal mostra antes de apagar."""
        return DemoDataSummary(
            datasets=await self._count(Dataset),
            inspections=await self._count(Inspection),
            model_metrics=await self._count(ModelMetric),
            sap_notes=await self._count(SapNote),
        )

    async def clear(self) -> DemoDataSummary:
        """Apaga **apenas** o que tem `source="seed"`. Coleta real fica.

        A ordem é filha antes de mãe. As FKs têm `ON DELETE CASCADE` e o
        Postgres daria conta sozinho, mas o SQLite dos testes desliga chave
        estrangeira por padrão — o cascade que passa em produção deixaria
        órfãos na suíte, que é o pior lugar para uma diferença de banco
        aparecer.
        """
        removed = await self.summary()

        seed_inspections = select(Inspection.id).where(Inspection.source == DataSource.SEED)
        seed_datasets = select(Dataset.id).where(Dataset.source == DataSource.SEED)

        await self._session.execute(
            delete(Damage).where(Damage.inspection_id.in_(seed_inspections))
        )
        await self._session.execute(delete(SapNote).where(SapNote.source == DataSource.SEED))
        # Nota aberta a partir de inspeção de demonstração, mas gravada sem a
        # marca: sem esta segunda passada ela sobreviveria à inspeção que a
        # explica e viraria uma linha órfã na tela.
        await self._session.execute(
            delete(SapNote).where(SapNote.inspection_id.in_(seed_inspections))
        )
        await self._session.execute(
            delete(DatasetImage).where(DatasetImage.dataset_id.in_(seed_datasets))
        )

        paths = (
            (await self._session.execute(
                select(Dataset.storage_path).where(Dataset.source == DataSource.SEED)
            ))
            .scalars()
            .all()
        )

        await self._session.execute(delete(Inspection).where(Inspection.source == DataSource.SEED))
        await self._session.execute(delete(Dataset).where(Dataset.source == DataSource.SEED))
        await self._session.execute(
            delete(ModelMetric).where(ModelMetric.source == DataSource.SEED)
        )
        await self._session.commit()

        for path in paths:
            await asyncio.to_thread(_remove_demo_dir, path)

        log.info(
            "demo_data_cleared",
            datasets=removed.datasets,
            inspections=removed.inspections,
            model_metrics=removed.model_metrics,
            sap_notes=removed.sap_notes,
        )
        return removed

    async def _count(self, model: type) -> int:
        from sqlalchemy import func

        return (
            await self._session.scalar(
                select(func.count()).select_from(model).where(model.source == DataSource.SEED)
            )
        ) or 0


def _remove_demo_dir(storage_path: str) -> None:
    """Apaga a pasta do dataset de demonstração, se ela existir mesmo.

    O seed grava um `storage_path` plausível sem criar nada em disco, então na
    maioria das vezes não há o que remover. A checagem de que o caminho está
    **dentro** de `DATASETS_DIR` não é paranoia gratuita: `storage_path` é uma
    string do banco, e um `rmtree` guiado por string do banco sem âncora é a
    forma clássica de apagar a raiz por engano.
    """
    try:
        path = Path(storage_path).resolve()
        root = settings.datasets_dir.resolve()
        if path.is_dir() and path != root and root in path.parents:
            shutil.rmtree(path)
            log.info("demo_dataset_dir_removed", path=str(path))
    except OSError as exc:  # pragma: no cover — disco em estado incomum
        log.warning("demo_dataset_dir_falhou", path=storage_path, error=str(exc))
