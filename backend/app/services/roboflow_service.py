"""Envio de um dataset ao Roboflow, preservando a partição.

O frontend dispara e acompanha. Quem monta o lote, respeita o split temporal,
lida com falha parcial e sabe de onde retomar é este serviço.

Não bloqueia a requisição
-------------------------
`start()` valida, cria a tarefa e devolve `202` na hora. O envio de 500 imagens
leva minutos; segurar a resposta HTTP até o fim deixaria a tela travada e o
navegador desistiria por timeout muito antes.

A tarefa roda no próprio laço de eventos, não numa thread: cada imagem é I/O de
rede aguardável (`httpx.AsyncClient`), e uma thread só faria sentido com um
cliente síncrono — que é o motivo de o M4TD ter usado uma. A sessão de banco é
própria da tarefa, porque a da requisição fecha quando a resposta é enviada.

Falha parcial não aborta o lote
-------------------------------
Uma imagem que falha é registrada na própria linha (`roboflow_error`) e o lote
continua. Cada sucesso marca `roboflow_sent_at`, e é isso que permite retomar:
subiram 300 de 500, o próximo envio começa da 301. Dez falhas seguidas param a
execução — nesse ponto o problema não é do arquivo, e insistir 500 vezes só
demora mais.

Frames em embargo não sobem. Enviá-los desfaria o embargo do outro lado.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, RoboflowNotConfiguredError
from app.core.events import bus
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.integrations.roboflow.client import (
    DEFAULT_TAG,
    RoboflowClient,
    RoboflowTarget,
    scrub,
)
from app.models.dataset import Dataset, DatasetImage
from app.models.enums import RoboflowStatus
from app.schemas.dataset import RoboflowUploadRequest, RoboflowUploadResult
from app.services.dataset_service import DatasetService
from app.services.roboflow_credentials_service import RoboflowCredentialService

log = get_logger(__name__)

MAX_CONSECUTIVE_FAILURES = 10
PROGRESS_EVERY = 10
"""Imagens entre dois eventos de progresso. Um por imagem inundaria o SSE."""


class _Run:
    """Uma execução em andamento. Vive em memória, uma por processo."""

    def __init__(self, dataset_id: int, total: int, batch: str, tags: list[str]) -> None:
        self.dataset_id = dataset_id
        self.total = total
        self.batch = batch
        self.tags = tags
        self.uploaded = 0
        self.failed = 0
        self.current: str | None = None
        self.cancel = asyncio.Event()
        self.task: asyncio.Task[None] | None = None


_runs: dict[int, _Run] = {}


class RoboflowService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._datasets = DatasetService(session)
        self._credentials = RoboflowCredentialService(session)

    # --- disparo --------------------------------------------------------------

    async def start(self, dataset_id: int, payload: RoboflowUploadRequest) -> RoboflowUploadResult:
        dataset = await self._datasets.assert_ready_for_upload(dataset_id)
        target = await self._resolve_target(payload)

        pending = await self._pending(dataset_id)
        if not pending:
            raise ConflictError(
                "Não há imagens pendentes: todas as partições já subiram ou o split "
                "ainda não foi feito."
            )

        batch = (payload.batch_name or "").strip() or dataset.version
        tags = [tag.strip() for tag in (payload.tags or []) if tag.strip()] or [
            dataset.version,
            DEFAULT_TAG,
        ]

        dataset.roboflow_status = RoboflowStatus.UPLOADING
        dataset.roboflow_error = None
        dataset.roboflow_batch = batch
        await self._session.commit()

        run = _Run(dataset_id, len(pending), batch, tags)
        _runs[dataset_id] = run
        run.task = asyncio.create_task(
            _upload_all(run, target, Path(dataset.storage_path), [row.id for row in pending])
        )

        await bus.publish("roboflow.started", dataset_id=dataset_id, total=run.total)
        log.info(
            "roboflow_started",
            dataset_id=dataset_id,
            total=run.total,
            workspace=target.workspace,
            project=target.project,
            batch=batch,
        )
        return self._result(dataset, run)

    async def cancel(self, dataset_id: int) -> RoboflowUploadResult:
        run = _runs.get(dataset_id)
        if run is None:
            raise ConflictError("Nenhum envio em andamento para este dataset.")
        run.cancel.set()
        dataset = await self._datasets.get(dataset_id)
        return self._result(dataset, run)

    async def status(self, dataset_id: int) -> RoboflowUploadResult:
        dataset = await self._datasets.get(dataset_id)
        return self._result(dataset, _runs.get(dataset_id))

    # --- apoio ----------------------------------------------------------------

    async def _resolve_target(self, payload: RoboflowUploadRequest) -> RoboflowTarget:
        """Credencial salva, credencial nova ou a do ambiente — nessa ordem."""
        if payload.credential_id is not None:
            return await self._credentials.target(payload.credential_id)

        if payload.api_key and payload.workspace and payload.project:
            if payload.save_credential:
                from app.schemas.dataset import RoboflowCredentialCreate

                await self._credentials.create(
                    RoboflowCredentialCreate(
                        label=payload.label or f"{payload.workspace}/{payload.project}",
                        workspace=payload.workspace,
                        project=payload.project,
                        api_key=payload.api_key,
                    )
                )
            return RoboflowTarget(
                workspace=payload.workspace, project=payload.project, api_key=payload.api_key
            )

        if not settings.roboflow_configured:
            raise RoboflowNotConfiguredError(
                "Escolha uma credencial salva ou informe workspace, projeto e chave."
            )
        return RoboflowTarget(
            workspace=settings.roboflow_workspace,
            project=settings.roboflow_project,
            api_key=settings.roboflow_api_key,
        )

    async def _pending(self, dataset_id: int) -> list[DatasetImage]:
        """As que faltam: com partição, fora do embargo e ainda não enviadas."""
        return list(
            (
                await self._session.execute(
                    select(DatasetImage)
                    .where(
                        DatasetImage.dataset_id == dataset_id,
                        DatasetImage.embargoed.is_(False),
                        DatasetImage.split.is_not(None),
                        DatasetImage.roboflow_sent_at.is_(None),
                    )
                    .order_by(DatasetImage.split, DatasetImage.frame_number)
                )
            ).scalars().all()
        )

    def _result(self, dataset: Dataset, run: _Run | None) -> RoboflowUploadResult:
        active = run is not None and run.task is not None and not run.task.done()
        return RoboflowUploadResult(
            dataset_id=dataset.id,
            status=dataset.roboflow_status,
            uploaded=run.uploaded if run else dataset.roboflow_uploaded,
            failed=run.failed if run else dataset.roboflow_failed,
            pending=max((run.total - run.uploaded - run.failed), 0) if run else 0,
            total=run.total if run else dataset.image_count,
            batch_name=dataset.roboflow_batch,
            tags=run.tags if run else [],
            current_file=run.current if active else None,
            message=dataset.roboflow_error,
            active=active,
        )


# --- execução ----------------------------------------------------------------


async def _upload_all(
    run: _Run, target: RoboflowTarget, base: Path, image_ids: list[int]
) -> None:
    """Sobe imagem a imagem, com sessão de banco própria.

    A sessão da requisição já foi fechada quando esta tarefa começa a rodar —
    por isso a tarefa abre a sua. É também o que mantém o commit por imagem
    fora da transação do endpoint.
    """
    client = RoboflowClient(target)
    consecutive = 0
    stopped: str | None = None

    async with SessionLocal() as session, httpx.AsyncClient() as http:
        for image_id in image_ids:
            if run.cancel.is_set():
                stopped = "cancelado pelo operador"
                break

            image = await session.get(DatasetImage, image_id)
            if image is None or image.split is None:
                continue  # excluída entre a montagem da lista e a vez dela

            path = base / str(image.split) / "images" / image.filename
            run.current = image.filename
            if not path.is_file():
                image.roboflow_error = "arquivo não existe mais em disco"
                run.failed += 1
                await session.commit()
                continue

            try:
                await client.upload_image(
                    http, path, split=str(image.split), batch=run.batch, tags=run.tags
                )
            except Exception as exc:  # noqa: BLE001 — falha parcial não aborta o lote
                consecutive += 1
                run.failed += 1
                # `scrub` mesmo para exceções que deveriam ser seguras: esta
                # mensagem vai para o banco e para a tela, e nenhuma biblioteca
                # promete não ecoar a URL — que carrega a chave.
                reason = scrub(str(exc))[:300]
                image.roboflow_error = reason
                await session.commit()
                log.warning("roboflow_image_failed", image=image.filename, error=reason[:200])
                if consecutive >= MAX_CONSECUTIVE_FAILURES:
                    stopped = (
                        f"{consecutive} falhas seguidas — envio interrompido. "
                        f"Último erro: {reason[:150]} Corrija o problema e clique em enviar "
                        "de novo: as imagens já enviadas não sobem outra vez."
                    )
                    break
                continue

            consecutive = 0
            run.uploaded += 1
            image.roboflow_sent_at = datetime.now(UTC)
            image.roboflow_error = None
            await session.commit()

            if run.uploaded % PROGRESS_EVERY == 0:
                await bus.publish(
                    "roboflow.progress",
                    dataset_id=run.dataset_id,
                    uploaded=run.uploaded,
                    failed=run.failed,
                    total=run.total,
                )

        await _finish(session, run, stopped)

    _runs.pop(run.dataset_id, None)


async def _finish(session: AsyncSession, run: _Run, stopped: str | None) -> None:
    dataset = await session.get(Dataset, run.dataset_id)
    if dataset is None:  # pragma: no cover — excluído durante o envio
        return

    dataset.roboflow_uploaded += run.uploaded
    dataset.roboflow_failed = run.failed
    dataset.roboflow_sent_at = datetime.now(UTC)

    remaining = await session.scalar(
        select(DatasetImage)
        .where(
            DatasetImage.dataset_id == run.dataset_id,
            DatasetImage.embargoed.is_(False),
            DatasetImage.split.is_not(None),
            DatasetImage.roboflow_sent_at.is_(None),
        )
        .limit(1)
    )

    if stopped:
        dataset.roboflow_status = RoboflowStatus.FAILED
        dataset.roboflow_error = stopped
    elif remaining is not None or run.failed:
        # Parcial é `failed` de propósito: um dataset incompleto no Roboflow
        # tem que aparecer diferente de um completo, senão alguém treina com
        # 60% das imagens sem saber.
        dataset.roboflow_status = RoboflowStatus.FAILED
        dataset.roboflow_error = (
            f"{run.failed} imagem(ns) falharam. Clique em enviar de novo para retomar "
            "de onde parou — as já enviadas não sobem outra vez."
        )
    else:
        dataset.roboflow_status = RoboflowStatus.SENT
        dataset.roboflow_error = None

    await session.commit()
    await bus.publish(
        "roboflow.finished",
        dataset_id=run.dataset_id,
        uploaded=run.uploaded,
        failed=run.failed,
        status=str(dataset.roboflow_status),
    )
    log.info(
        "roboflow_finished",
        dataset_id=run.dataset_id,
        uploaded=run.uploaded,
        failed=run.failed,
        status=str(dataset.roboflow_status),
    )
