"""Consulta e edição de datasets: galeria, exclusão e resplit.

Duas fontes, uma verdade cada
-----------------------------
* O **banco** guarda o que a coleta produziu e como o split rotulou cada
  quadro. É o que a listagem e a galeria leem.
* O **disco** é a verdade sobre o que existe agora. As contagens exibidas no
  detalhe são contadas na hora (`live_counts`), e a divergência com o
  manifesto é mostrada (`drifted`), não escondida.

O manifesto é imutável entre splits: excluir imagem não o reescreve. Ele
registra um evento — o que o split decidiu —, não o conteúdo atual das pastas.
Reescrevê-lo a cada exclusão faria o dataset deixar de ser reproduzível, que é
a única razão de ele existir.

Excluir muda a proporção
------------------------
Tirar 40 imagens de `train` desloca a divisão de 70/15/15 para outra coisa. O
detalhe mostra as contagens novas e oferece **refazer o split** a partir de
`raw/` — é exatamente por isso que a pasta original é mantida.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.dataset import Dataset, DatasetImage
from app.models.enums import CollectionStatus, RoboflowStatus, SplitName
from app.schemas.common import Page
from app.schemas.dataset import (
    DatasetDetail,
    DatasetImageOut,
    DatasetSummary,
    DeleteImagesResult,
    ResplitResult,
    SplitCounts,
    SplitDistribution,
    SplitWarningOut,
)
from app.services import dataset_storage as storage
from app.services import split_runner

log = get_logger(__name__)

ACTIVE_COLLECTION = (CollectionStatus.RECORDING, CollectionStatus.PAUSED)


def _distribution(dataset: Dataset) -> SplitDistribution:
    return SplitDistribution(
        train=dataset.train_count,
        valid=dataset.valid_count,
        test=dataset.test_count,
        embargo_seconds=dataset.embargo_seconds,
        embargo_frames=dataset.embargo_frames,
        embargoed=dataset.embargoed_count,
    )


def _to_summary(dataset: Dataset) -> DatasetSummary:
    return DatasetSummary(
        id=dataset.id,
        version=dataset.version,
        started_at=dataset.started_at,
        duration_seconds=dataset.duration_seconds,
        image_count=dataset.image_count,
        disk_bytes=dataset.disk_bytes,
        status=dataset.status,
        distribution=_distribution(dataset),
        roboflow_status=dataset.roboflow_status,
        roboflow_sent_at=dataset.roboflow_sent_at,
        source=dataset.source,
    )


def _image_out(dataset_id: int, row: DatasetImage) -> DatasetImageOut:
    return DatasetImageOut(
        id=row.id,
        filename=row.filename,
        captured_at=row.captured_at,
        frame_number=row.frame_number,
        width=row.width,
        height=row.height,
        size_bytes=row.size_bytes,
        split=row.split,
        embargoed=row.embargoed,
        roboflow_sent_at=row.roboflow_sent_at,
        url=f"/api/v1/datasets/{dataset_id}/images/{row.id}/raw",
        thumb_url=f"/api/v1/datasets/{dataset_id}/images/{row.id}/thumb",
    )


class DatasetService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, page: int = 1, page_size: int = 50) -> Page[DatasetSummary]:
        total = await self._session.scalar(select(func.count(Dataset.id))) or 0
        rows = (
            await self._session.execute(
                select(Dataset)
                .order_by(Dataset.started_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return Page(
            items=[_to_summary(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get(self, dataset_id: int) -> Dataset:
        dataset = await self._session.get(Dataset, dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset {dataset_id} não encontrado.")
        return dataset

    async def detail(self, dataset_id: int) -> DatasetDetail:
        dataset = await self.get(dataset_id)
        base = Path(dataset.storage_path)
        counts = (
            await asyncio.to_thread(storage.live_counts, base)
            if base.is_dir()
            else {"train": 0, "valid": 0, "test": 0, "raw": 0, "total": 0}
        )
        manifest = await asyncio.to_thread(split_runner.read_manifest, base)
        warnings = [SplitWarningOut(**item) for item in (manifest or {}).get("warnings", [])]

        return DatasetDetail(
            **_to_summary(dataset).model_dump(),
            storage_path=dataset.storage_path,
            ended_at=dataset.ended_at,
            roboflow_error=dataset.roboflow_error,
            sample_interval_seconds=dataset.sample_interval_seconds,
            frame_limit=dataset.frame_limit,
            dedup_enabled=dataset.dedup_enabled,
            dedup_skipped=dataset.dedup_skipped,
            split_at=dataset.split_at,
            counts=SplitCounts(**counts),
            warnings=warnings,
            drifted=_drifted(manifest, counts),
        )

    async def images(
        self,
        dataset_id: int,
        split: SplitName | None = None,
        page: int = 1,
        page_size: int = 60,
    ) -> Page[DatasetImageOut]:
        """Imagens **cruas**. A página Datasets nunca mostra saída do modelo."""
        await self.get(dataset_id)
        criteria = [DatasetImage.dataset_id == dataset_id]
        if split is not None:
            criteria.append(DatasetImage.split == split)

        total = (
            await self._session.scalar(select(func.count(DatasetImage.id)).where(*criteria)) or 0
        )
        rows = (
            await self._session.execute(
                select(DatasetImage)
                .where(*criteria)
                .order_by(DatasetImage.frame_number)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return Page(
            items=[_image_out(dataset_id, row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def image(self, dataset_id: int, image_id: int) -> DatasetImage:
        row = await self._session.get(DatasetImage, image_id)
        if row is None or row.dataset_id != dataset_id:
            raise NotFoundError(f"Imagem {image_id} não existe no dataset {dataset_id}.")
        return row

    async def image_file(self, dataset_id: int, image_id: int, thumb: bool) -> Path:
        """Caminho no disco. `thumb=True` gera e cacheia a miniatura de 240 px.

        A grade pede miniatura; o visor pede o arquivo inteiro. Mandar 500
        JPEGs em tamanho real para montar uma grade trava o navegador — e é o
        tipo de coisa que só aparece na primeira coleta grande de verdade.
        """
        dataset = await self.get(dataset_id)
        row = await self.image(dataset_id, image_id)
        base = Path(dataset.storage_path)
        split = str(row.split) if row.split else None
        if thumb:
            return await asyncio.to_thread(storage.thumb_path, base, split, row.filename)
        return await asyncio.to_thread(storage.image_path, base, split, row.filename)

    # --- edição ---------------------------------------------------------------

    async def delete_images(self, dataset_id: int, image_ids: list[int]) -> DeleteImagesResult:
        """Apaga da partição **e** de `raw/`.

        Apagar só da partição faria o "refazer o split a partir de `raw/`" —
        oferecido justamente porque as proporções mudaram — ressuscitar tudo
        que o operador acabou de excluir. Entre a irreversibilidade e um botão
        que desfaz o trabalho de quem clicou, a irreversibilidade é o mal
        menor; por isso o modal diz, em palavras, que não dá para desfazer.
        """
        dataset = await self._guard_editable(dataset_id, "excluir imagens")
        base = Path(dataset.storage_path)

        rows = (
            await self._session.execute(
                select(DatasetImage).where(
                    DatasetImage.dataset_id == dataset_id, DatasetImage.id.in_(image_ids)
                )
            )
        ).scalars().all()
        if not rows:
            raise NotFoundError("Nenhuma das imagens indicadas existe neste dataset.")

        removed = 0
        for row in rows:
            await asyncio.to_thread(
                storage.delete_image_files, base, str(row.split) if row.split else None, row.filename
            )
            await self._session.delete(row)
            removed += 1

        await self._session.flush()
        await self._recount(dataset)
        await self._session.commit()

        counts = await asyncio.to_thread(storage.live_counts, base)
        manifest = await asyncio.to_thread(split_runner.read_manifest, base)
        log.info("dataset_images_deleted", dataset_id=dataset_id, removed=removed)
        return DeleteImagesResult(
            removed=removed,
            counts=SplitCounts(**counts),
            distribution=_distribution(dataset),
            drifted=_drifted(manifest, counts),
        )

    async def delete_dataset(self, dataset_id: int, confirm: str) -> None:
        """Apaga a versão inteira. Exige digitar a versão, sem espaço para engano."""
        dataset = await self._guard_editable(dataset_id, "excluir o dataset")
        if confirm.strip() != dataset.version:
            raise ConflictError(
                f"Para excluir, digite exatamente {dataset.version}."
            )
        base = Path(dataset.storage_path)
        if base.is_dir():
            await asyncio.to_thread(storage.delete_version, base)
        await self._session.delete(dataset)
        await self._session.commit()
        log.info("dataset_deleted", dataset_id=dataset_id, version=dataset.version)

    async def prune_empty(self) -> list[str]:
        """Remove coletas encerradas que não têm imagem nenhuma. Devolve as versões.

        Resíduo de antes de o descarte automático existir: `v0.4`, `v0.5` e
        `v0.6` eram sessões que iniciaram e não salvaram quadro nenhum. Cada
        uma ocupa um número de versão que `next_version()` respeita, então a
        primeira coleta de verdade depois delas sai três números à frente sem
        nada ter sido coletado.

        A guarda é dupla — `image_count == 0` **e** `raw/` vazio em disco —
        porque as duas fontes discordam justamente quando o banco perdeu uma
        linha: apagar guiado só pelo contador destruiria um voo que existe em
        disco. Coleta em andamento nunca entra: só `saved` e `cancelled`.
        """
        rows = (
            await self._session.execute(
                select(Dataset).where(
                    Dataset.image_count == 0,
                    Dataset.status.in_((CollectionStatus.SAVED, CollectionStatus.CANCELLED)),
                )
            )
        ).scalars().all()

        removed: list[str] = []
        for dataset in rows:
            base = Path(dataset.storage_path)
            if base.is_dir() and await asyncio.to_thread(storage.live_counts, base) != {
                "train": 0,
                "valid": 0,
                "test": 0,
                "raw": 0,
                "total": 0,
            }:
                log.warning(
                    "dataset_vazio_com_arquivos",
                    version=dataset.version,
                    path=str(base),
                    motivo="há imagens em disco que o banco não conhece — não foi removido",
                )
                continue
            if base.is_dir():
                await asyncio.to_thread(storage.delete_version, base)
            await self._session.delete(dataset)
            removed.append(dataset.version)
            log.info(
                "dataset_vazio_removido",
                version=dataset.version,
                path=str(base),
                motivo="coleta encerrada sem nenhum quadro",
            )

        await self._session.commit()
        return removed

    async def resplit(self, dataset_id: int) -> ResplitResult:
        """Refaz a partição a partir de `raw/`, no estado em que `raw/` está agora.

        É o mesmo `split_runner.run()` do Salvar, sem variante nenhuma: as
        partições são apagadas e reescritas e o manifesto é sobrescrito com a
        decisão nova. Depois de excluir imagens é a única forma de as
        proporções voltarem a valer.
        """
        dataset = await self._guard_editable(dataset_id, "refazer o split")
        base = Path(dataset.storage_path)
        if not base.is_dir():
            raise NotFoundError(f"A pasta de {dataset.version} não existe mais em disco.")

        manifest = await asyncio.to_thread(split_runner.run, base, None, None)

        rows = (
            await self._session.execute(
                select(DatasetImage).where(DatasetImage.dataset_id == dataset_id)
            )
        ).scalars().all()
        _apply_manifest_to_rows(rows, manifest)

        counts = manifest["counts"]
        dataset.train_count = counts["train"]
        dataset.valid_count = counts["valid"]
        dataset.test_count = counts["test"]
        dataset.embargoed_count = counts["embargoed"]
        dataset.embargo_seconds = manifest["embargo"]["seconds"]
        dataset.embargo_frames = manifest["embargo"]["frames_applied"]
        dataset.image_count = len(rows)
        dataset.split_at = datetime.now(UTC)
        await self._session.commit()

        live = await asyncio.to_thread(storage.live_counts, base)
        log.info("dataset_resplit", dataset_id=dataset_id, version=dataset.version, **counts)
        return ResplitResult(
            version=dataset.version,
            counts=SplitCounts(**live),
            distribution=_distribution(dataset),
            warnings=[SplitWarningOut(**item) for item in manifest["warnings"]],
        )

    # --- guardas --------------------------------------------------------------

    async def _guard_editable(self, dataset_id: int, action: str) -> Dataset:
        """Recusa mexer num dataset que ainda está gravando ou subindo.

        Um resplit move arquivos entre partições; no meio de um envio, o
        uploader passaria a procurar caminhos que deixaram de existir.
        """
        dataset = await self.get(dataset_id)
        if dataset.status in ACTIVE_COLLECTION:
            raise ConflictError(f"A coleta {dataset.version} ainda está aberta — salve antes de {action}.")
        if dataset.roboflow_status in (RoboflowStatus.QUEUED, RoboflowStatus.UPLOADING):
            raise ConflictError(
                f"Há um envio de {dataset.version} ao Roboflow em andamento — "
                f"cancele antes de {action}."
            )
        return dataset

    async def _recount(self, dataset: Dataset) -> None:
        """Reconta a distribuição a partir das linhas que sobraram."""
        rows = (
            await self._session.execute(
                select(DatasetImage.split, func.count(DatasetImage.id))
                .where(DatasetImage.dataset_id == dataset.id)
                .group_by(DatasetImage.split)
            )
        ).all()
        counts = {str(split) if split else "embargoed": total for split, total in rows}
        dataset.train_count = counts.get("train", 0)
        dataset.valid_count = counts.get("valid", 0)
        dataset.test_count = counts.get("test", 0)
        dataset.embargoed_count = counts.get("embargoed", 0)
        dataset.image_count = sum(counts.values())

    async def assert_ready_for_upload(self, dataset_id: int) -> Dataset:
        dataset = await self.get(dataset_id)
        if dataset.status != CollectionStatus.SAVED:
            raise ConflictError("Salve a coleta antes de enviar para o Roboflow.")
        if dataset.roboflow_status in (RoboflowStatus.QUEUED, RoboflowStatus.UPLOADING):
            raise ConflictError("Este dataset já está sendo enviado.")
        return dataset


def _drifted(manifest: dict | None, counts: dict[str, int]) -> bool:
    """O disco divergiu do que o **manifesto** decidiu?

    A comparação é com o manifesto, não com as colunas do dataset: as colunas
    são recontadas a cada exclusão e por isso nunca divergem — elas seguem o
    disco. Quem fica para trás de propósito é o manifesto, que registra o
    evento do split e não é reescrito. A diferença entre os dois é justamente o
    que o operador precisa ver para decidir refazer o split.
    """
    if not manifest:
        return False
    expected = manifest.get("counts") or {}
    return any(counts[name] != expected.get(name) for name in storage.SPLITS)


def _apply_manifest_to_rows(rows: list[DatasetImage], manifest: dict) -> None:
    """Reetiqueta as linhas com a decisão do manifesto recém-escrito."""
    assigned: dict[str, str | None] = {}
    for split in storage.SPLITS:
        for entry in manifest["files"].get(split, []):
            assigned[entry["file"]] = split
    for entry in manifest["files"].get("embargoed", []):
        assigned[entry["file"]] = None

    for row in rows:
        split = assigned.get(row.filename)
        row.split = SplitName(split) if split else None
        row.embargoed = row.filename in assigned and split is None
        row.relative_path = (
            f"{split}/images/{row.filename}" if split else f"{storage.RAW_DIR}/{row.filename}"
        )
