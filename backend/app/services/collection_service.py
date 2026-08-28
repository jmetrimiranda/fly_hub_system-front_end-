"""Coleta de imagens: guarda, iniciar, pausar, retomar, salvar.

A máquina de estados é a mesma que os botões da página Voo mostram:

    ocioso ──Confirmar──▶ gravando ⇄ pausado
                              │          │
                              └──Salvar──┘
                                    │
                                    ▼
                                  salvo ──▶ ocioso

Duas metades
------------
* **Disco e threads** ficam em `collection_runtime.py`: amostragem, dedup,
  escrita, `session.json`. É o que não pode ser `async`.
* **Banco e regra** ficam aqui. O banco é escrito uma vez, no Salvar. Durante
  a gravação a verdade é o disco, e a interface lê os contadores do gravador.

Salvar é o único ponto em que o split temporal roda. Antes disso o dataset
existe em disco mas ainda não é uma versão particionada.

A guarda
--------
`preflight()` roda duas vezes: o botão a consulta antes de abrir o modal, e o
`start()` a repete. Não é redundância — a interface pode estar olhando um
estado de dois segundos atrás, e o disco pode ter enchido nesse intervalo. Um
botão clicável que falha depois é pior que um botão desabilitado que explica.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import CollectionStateError, PreflightError
from app.core.events import bus
from app.core.logging import get_logger
from app.integrations.flyhub.client import FlyHubClient
from app.models.dataset import Dataset, DatasetImage
from app.models.enums import CollectionStatus, SplitName
from app.schemas.flight import (
    CollectionDefaults,
    CollectionPreflight,
    CollectionProgress,
    CollectionSession,
    CollectionStart,
    PreflightCheck,
)
from app.services import dataset_storage as storage
from app.services import split_runner
from app.services.collection_runtime import INTERVAL_OPTIONS, recorder

log = get_logger(__name__)

ACTIVE_STATES = (CollectionStatus.RECORDING, CollectionStatus.PAUSED)


class CollectionService:
    def __init__(self, session: AsyncSession, client: FlyHubClient | None = None) -> None:
        self._session = session
        self._client = client or FlyHubClient()

    # --- guarda ---------------------------------------------------------------

    async def preflight(self) -> CollectionPreflight:
        """As condições que a gravação exige, cada uma com a instrução do erro."""
        probe = await self._client.probe(settings.flyhub_stream_path)
        tunnel_up = await self._client.tunnel_up()
        disk = storage.disk_usage()

        stream_ready = probe.broker_up and probe.stream.ready
        disk_ok = disk.ok and not disk.over_limit

        checks = [
            PreflightCheck(
                key="stream",
                label="Stream",
                ok=stream_ready,
                detail=(
                    settings.flyhub_stream_path if stream_ready else "nenhum path ativo"
                ),
                fix=(
                    None
                    if stream_ready
                    else "Confira o endereço no FlightHub e religue o toggle do canal."
                ),
            ),
            PreflightCheck(
                key="mediamtx",
                label="MediaMTX",
                ok=probe.broker_up,
                detail="no ar, API respondendo" if probe.broker_up else "fora do ar",
                fix=(
                    None
                    if probe.broker_up
                    else "Suba o MediaMTX e confirme MEDIAMTX_API_URL no .env."
                ),
            ),
            PreflightCheck(
                key="tunnel",
                label="Túnel",
                ok=tunnel_up or bool(settings.flyhub_public_host),
                blocking=False,
                detail=self._tunnel_detail(tunnel_up),
                fix=None,
            ),
            PreflightCheck(
                key="disk",
                label="Disco",
                ok=disk_ok,
                detail=(
                    f"{disk.percent:.0f}% usado · {disk.free_bytes // 1_048_576} MB livres"
                    if disk.ok
                    else (disk.error or "indisponível")
                ),
                fix=(
                    None
                    if disk_ok
                    else f"Acima de {disk.limit_pct:.0f}% a coleta não inicia. "
                    "Libere espaço em data/datasets."
                ),
            ),
        ]

        failed = [check for check in checks if check.blocking and not check.ok]
        return CollectionPreflight(
            ok=not failed,
            checks=checks,
            failed=failed,
            next_version=await self._next_version(),
            disk_percent=disk.percent,
            disk_free_bytes=disk.free_bytes,
            disk_limit_pct=disk.limit_pct,
            defaults=CollectionDefaults(
                interval_seconds=settings.collect_interval_seconds,
                interval_options=list(INTERVAL_OPTIONS),
                frame_limit=settings.collect_frame_limit,
                dedup=True,
                dedup_threshold=settings.dedup_threshold,
            ),
        )

    async def _next_version(self) -> str:
        """A próxima versão livre **em disco e no banco**.

        As duas listas, e não só a do disco: a coluna `version` é única, e uma
        linha cuja pasta sumiu continua ocupando o número.
        """
        known = (await self._session.execute(select(Dataset.version))).scalars().all()
        return await asyncio.to_thread(storage.next_version, known)

    @staticmethod
    def _tunnel_detail(tunnel_up: bool) -> str:
        if tunnel_up:
            return settings.tunnel_public_host
        if settings.flyhub_public_host:
            return f"dispensado — {settings.flyhub_public_host}"
        return "desligado"

    # --- estado ---------------------------------------------------------------

    async def _active_row(self) -> Dataset | None:
        """A linha da coleta aberta, já reconciliada com o gravador.

        A reconciliação não é enfeite. A auto-pausa — disco cheio, limite de
        quadros — acontece dentro da thread do gravador, que não pode escrever
        no banco. Sem trazer esse estado para a linha antes de qualquer guarda,
        `Continuar` batia num 409 dizendo que a coleta estava "em recording e a
        ação exige paused", com a tela mostrando PAUSADO ao lado.
        """
        result = await self._session.execute(
            select(Dataset).where(Dataset.status.in_(ACTIVE_STATES)).limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        status = recorder.status()
        if status.active and status.version == row.version and row.status != status.status:
            row.status = status.status or row.status
            await self._session.commit()
        return row

    async def current(self) -> CollectionSession | None:
        """A coleta em curso, com os contadores vindos do gravador em memória."""
        row = await self._active_row()
        if row is None:
            return None
        return self._to_schema(row)

    def _to_schema(self, row: Dataset) -> CollectionSession:
        session = CollectionSession.model_validate(row)
        status = recorder.status()
        if status.active and status.version == row.version:
            session.status = status.status or row.status
            session.image_count = status.saved
            session.disk_bytes = status.bytes
            session.duration_seconds = int(status.elapsed_seconds)
            session.dedup_skipped = status.dedup_skipped
            session.progress = CollectionProgress(
                saved=status.saved,
                bytes=status.bytes,
                elapsed_seconds=status.elapsed_seconds,
                dedup_skipped=status.dedup_skipped,
                stale_skipped=status.stale_skipped,
                io_dropped=status.io_dropped,
                write_errors=status.write_errors,
                queue_depth=status.queue_depth,
                last_file=status.last_file,
                paused_reason=status.paused_reason,
                error=status.error,
                disk_percent=status.disk_percent,
                disk_free_bytes=status.disk_free_bytes,
                disk_over_limit=status.disk_over_limit,
            )
        return session

    # --- transições -----------------------------------------------------------

    async def start(self, payload: CollectionStart) -> CollectionSession:
        if await self._active_row() or recorder.active:
            raise CollectionStateError("Já existe uma coleta em andamento.")

        check = await self.preflight()
        if not check.ok:
            raise PreflightError(
                "Não é possível iniciar a coleta.",
                checks=[item.model_dump() for item in check.checks],
                failed=[item.model_dump() for item in check.failed],
            )
        if payload.interval_seconds not in INTERVAL_OPTIONS:
            raise CollectionStateError(
                f"Intervalo inválido. Use um de: {', '.join(str(o) for o in INTERVAL_OPTIONS)} s."
            )

        version = check.next_version
        base = await asyncio.to_thread(storage.create_version, version)

        dataset = Dataset(
            version=version,
            started_at=datetime.now(UTC),
            status=CollectionStatus.RECORDING,
            storage_path=str(base),
            sample_interval_seconds=payload.interval_seconds,
            frame_limit=payload.frame_limit,
            dedup_enabled=payload.dedup,
        )
        self._session.add(dataset)
        try:
            await self._session.commit()
        except Exception:
            # A pasta é criada antes da linha (o gravador precisa dela pronta).
            # Se o INSERT falhar, ela fica órfã e a varredura de versões passa a
            # pular um número a cada tentativa — silenciosamente, porque a pasta
            # vazia parece um dataset. Desfaz.
            await self._session.rollback()
            await asyncio.to_thread(_remove_empty, base)
            raise
        await self._session.refresh(dataset)

        recorder.start(
            version=version,
            base=base,
            interval=payload.interval_seconds,
            limit=payload.frame_limit,
            dedup=payload.dedup,
        )

        await bus.publish("collection.started", dataset_id=dataset.id, version=version)
        log.info("collection_started", dataset_id=dataset.id, version=version, path=str(base))
        return self._to_schema(dataset)

    async def _require_active(self, expected: CollectionStatus) -> Dataset:
        dataset = await self._active_row()
        if dataset is None:
            raise CollectionStateError("Nenhuma coleta em andamento.")
        if dataset.status != expected:
            raise CollectionStateError(
                f"A coleta está em '{dataset.status}' e a ação exige '{expected}'."
            )
        return dataset

    async def pause(self) -> CollectionSession:
        dataset = await self._require_active(CollectionStatus.RECORDING)
        recorder.pause("pausado pelo operador")
        dataset.status = CollectionStatus.PAUSED
        await self._session.commit()
        await bus.publish("collection.paused", dataset_id=dataset.id)
        return self._to_schema(dataset)

    async def resume(self) -> CollectionSession:
        dataset = await self._require_active(CollectionStatus.PAUSED)
        disk = storage.disk_usage()
        if disk.over_limit:
            raise CollectionStateError(
                f"Disco em {disk.percent:.0f}% (limite {disk.limit_pct:.0f}%). "
                "Libere espaço antes de continuar."
            )
        recorder.resume()
        dataset.status = CollectionStatus.RECORDING
        await self._session.commit()
        await bus.publish("collection.resumed", dataset_id=dataset.id)
        return self._to_schema(dataset)

    async def save(self) -> CollectionSession:
        """Encerra a coleta, particiona `raw/` e popula o banco.

        A ordem é: parar a gravação, particionar em disco, só então escrever as
        linhas. Escrever antes do split obrigaria a um segundo UPDATE por
        imagem, e uma queda no meio deixaria linhas sem partição apontando para
        arquivos que ainda não existem.
        """
        dataset = await self._active_row()
        if dataset is None:
            raise CollectionStateError("Nenhuma coleta em andamento.")

        finished = await asyncio.to_thread(recorder.finish)
        if finished is None:
            raise CollectionStateError(
                "O gravador não está no ar — a coleta foi interrompida por um reinício "
                "do backend. Os quadros continuam em raw/; use Refazer split no dataset."
            )
        if not finished.records:
            return await self._discard_empty(dataset, "nenhum quadro foi gravado")
        now = datetime.now(UTC)
        dataset.ended_at = now
        dataset.duration_seconds = int((now - _aware(dataset.started_at)).total_seconds())

        base = Path(dataset.storage_path)
        session_doc = {
            "version": dataset.version,
            "interval_s": dataset.sample_interval_seconds,
            "limit": dataset.frame_limit,
            "dedup": dataset.dedup_enabled,
            "started_at": dataset.started_at.isoformat(),
            "ended_at": now.isoformat(),
        }
        manifest = await asyncio.to_thread(split_runner.run, base, None, session_doc)

        images = _rows_from_records(dataset, finished.records)
        self._session.add_all(images)
        _apply_manifest(images, manifest)

        dataset.dedup_skipped = finished.dedup_skipped
        dataset.io_dropped = finished.io_dropped
        _fill_counters(dataset, manifest, images)
        dataset.status = CollectionStatus.SAVED
        dataset.split_at = now

        await self._session.commit()
        await bus.publish(
            "collection.saved",
            dataset_id=dataset.id,
            version=dataset.version,
            train=dataset.train_count,
            valid=dataset.valid_count,
            test=dataset.test_count,
            embargoed=dataset.embargoed_count,
        )
        log.info(
            "collection_saved",
            dataset_id=dataset.id,
            images=dataset.image_count,
            embargoed=dataset.embargoed_count,
        )
        return CollectionSession.model_validate(dataset)

    async def cancel(self) -> CollectionSession:
        """Interrompe sem particionar. Os quadros ficam em `raw/`, recuperáveis.

        Apagar a pasta seria mais limpo na listagem e destruiria um voo inteiro
        num clique de quem quis apenas parar. Quem quiser mesmo se livrar dela
        usa "Excluir dataset", que exige digitar a versão.
        """
        dataset = await self._active_row()
        if dataset is None:
            raise CollectionStateError("Nenhuma coleta em andamento.")
        status = recorder.status()
        await asyncio.to_thread(recorder.abort)
        if status.saved == 0:
            return await self._discard_empty(dataset, "cancelada antes do primeiro quadro")
        dataset.status = CollectionStatus.CANCELLED
        dataset.ended_at = datetime.now(UTC)
        dataset.image_count = status.saved
        dataset.disk_bytes = status.bytes
        await self._session.commit()
        await bus.publish("collection.cancelled", dataset_id=dataset.id)
        return CollectionSession.model_validate(dataset)


    # --- resíduo --------------------------------------------------------------

    async def _discard_empty(self, dataset: Dataset, reason: str) -> CollectionSession:
        """Encerra uma coleta que não gravou quadro nenhum sem deixar rastro.

        Uma sessão que iniciou e não salvou nada não é um dataset: é uma
        tentativa. Mantê-la produz uma linha `v0.5` com zero imagens que não dá
        para enviar ao Roboflow, não dá para reparticionar e não explica nada —
        e, pior, **queima o número da versão**, porque `next_version()` respeita
        tanto a pasta quanto a coluna `version`. Depois de três tentativas a
        primeira coleta de verdade sai como `v0.6`, sem que nada tenha sido
        coletado antes.

        Apagar aqui é seguro justamente porque não há o que perder: sem quadro
        em `raw/` não existe voo para recuperar. O `cancel()` de uma coleta com
        imagens continua preservando tudo — a diferença é essa, e é o que o
        `reason` registra no log.
        """
        snapshot = CollectionSession.model_validate(dataset)
        snapshot.status = CollectionStatus.CANCELLED
        snapshot.image_count = 0
        snapshot.disk_bytes = 0
        snapshot.ended_at = datetime.now(UTC)

        base = Path(dataset.storage_path)
        version = dataset.version
        dataset_id = dataset.id

        await self._session.delete(dataset)
        await self._session.commit()
        await asyncio.to_thread(_remove_version, base)

        await bus.publish("collection.discarded", dataset_id=dataset_id, version=version)
        log.info(
            "collection_discarded",
            dataset_id=dataset_id,
            version=version,
            path=str(base),
            motivo=reason,
            versao_liberada=version,
        )
        return snapshot


def _remove_version(base: Path) -> None:
    """Apaga a pasta da versão descartada. Ausente já é o estado desejado."""
    try:
        storage.delete_version(base)
    except OSError as exc:  # pragma: no cover — disco em estado incomum
        log.warning("collection_discard_dir_falhou", path=str(base), error=str(exc))


def _remove_empty(base: Path) -> None:
    """Apaga a versão recém-criada se ela ainda não tiver quadro nenhum."""
    raw = base / storage.RAW_DIR
    if any(raw.iterdir()):  # pragma: no cover — nunca há quadro tão cedo
        return
    raw.rmdir()
    base.rmdir()


def _aware(value: datetime) -> datetime:
    """SQLite devolve datetime ingênuo mesmo em coluna `timezone=True`.

    O Postgres de produção devolve com fuso; os testes rodam em SQLite. Sem
    esta normalização a subtração estoura só na suíte, que é o pior lugar para
    uma diferença de ambiente aparecer.
    """
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# --- tradução disco → banco ---------------------------------------------------


def _rows_from_records(dataset: Dataset, records: list[dict[str, Any]]) -> list[DatasetImage]:
    """Uma linha por arquivo efetivamente gravado em `raw/`.

    `captured_at` vem do `epoch` do quadro, não do relógio de agora: é o
    instante da captura, e é o que faz a ordem no banco bater com a ordem que o
    split usou.
    """
    rows: list[DatasetImage] = []
    for record in records:
        rows.append(
            DatasetImage(
                dataset_id=dataset.id,
                filename=record["file"],
                relative_path=f"{storage.RAW_DIR}/{record['file']}",
                captured_at=datetime.fromtimestamp(record["epoch"], UTC),
                frame_number=record["index"],
                width=record.get("width"),
                height=record.get("height"),
                size_bytes=record.get("bytes", 0),
            )
        )
    return rows


def _apply_manifest(images: list[DatasetImage], manifest: dict[str, Any]) -> None:
    """Copia a decisão do split para as linhas, por nome de arquivo.

    O manifesto é a fonte: ele é o que ficou em disco, e é o que alguém vai ler
    daqui a seis meses para explicar por que um quadro está em `valid`.
    """
    assigned: dict[str, str | None] = {}
    for split in storage.SPLITS:
        for entry in manifest["files"].get(split, []):
            assigned[entry["file"]] = split
    for entry in manifest["files"].get("embargoed", []):
        assigned[entry["file"]] = None

    for image in images:
        split = assigned.get(image.filename)
        image.split = SplitName(split) if split else None
        image.embargoed = image.filename in assigned and split is None
        image.relative_path = (
            f"{split}/images/{image.filename}" if split else f"{storage.RAW_DIR}/{image.filename}"
        )


def _fill_counters(
    dataset: Dataset, manifest: dict[str, Any], images: list[DatasetImage]
) -> None:
    counts = manifest["counts"]
    dataset.train_count = counts["train"]
    dataset.valid_count = counts["valid"]
    dataset.test_count = counts["test"]
    dataset.embargoed_count = counts["embargoed"]
    dataset.embargo_seconds = manifest["embargo"]["seconds"]
    dataset.embargo_frames = manifest["embargo"]["frames_applied"]
    dataset.image_count = len(images)
    dataset.disk_bytes = sum(image.size_bytes for image in images)
