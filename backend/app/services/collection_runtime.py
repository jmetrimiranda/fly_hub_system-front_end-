"""Gravação de quadros em disco: amostragem, deduplicação e escrita.

Portado de `app/collect.py` do M4TD. É a parte da coleta que não pode ser
`async`: o leitor de vídeo vive em thread, o `imencode` é CPU e o `write` é
I/O bloqueante. O `CollectionService` fica com o banco e a máquina de estados;
aqui fica o laço.

```text
leitor RTSP ──► slot de 1 quadro ──► amostradora ──► fila ──► writers ──► raw/
                (quadro ORIGINAL,     decide e        limitada  nice+10
                 antes do detector)   nomeia                     JPEG q92
```

Exibir o vídeo é a função principal da tela; a coleta é secundária e nunca pode
degradá-la. Três mecanismos garantem isso:

1. **A amostradora nunca faz I/O.** Ela decide, atribui o índice e entrega o
   quadro para a fila. Encode e escrita ficam com os workers.
2. **Fila limitada.** Cheia, o quadro é descartado na hora e contabilizado como
   `io_dropped`, visível na interface. Nunca bloqueia a amostragem e nunca
   cresce sem teto: uma fila ilimitada trocaria latência por memória, e cada
   item é um quadro decodificado inteiro.
3. **Workers com prioridade rebaixada** (`os.nice`), no máximo dois. Na disputa
   por CPU com o encode do MJPEG, quem cede é a coleta.

De onde vem a imagem
--------------------
Do slot do **leitor**, não do slot de saída do worker de inferência. É a mesma
decisão da fronteira do projeto: Dataset mostra a imagem original, Voo mostra a
processada. Ler do slot de saída gravaria o quadro com a sobreposição desenhada
e contaminaria o treino seguinte com os erros do modelo anterior.

De onde vem o tempo
-------------------
De `frame.captured_at`, o relógio monotônico do leitor, e o `t` do nome do
arquivo é relativo ao **primeiro quadro salvo desta sessão**. Não se usa
`frame.elapsed`: ele conta desde `session_started_at`, que o leitor rezera a
cada reconexão do RTSP, e uma reconexão no meio do voo faria os nomes voltarem
para `t0.00` — quebrando o split temporal justamente no caso em que a
resolução em "Automático" torna comum.
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.vision import video
from app.models.enums import CollectionStatus
from app.services import dataset_storage as storage

log = get_logger(__name__)

INTERVAL_OPTIONS = (0.5, 1.0, 2.0, 5.0)

TICK_S = 0.1
"""Granularidade do laço da amostradora."""
DISK_CHECK_EVERY_S = 5.0
SESSION_FLUSH_EVERY_S = 2.0

DEDUP_SIZE = 128
"""Compara em 128×128 cinza: barato e imune a troca de resolução no meio."""


@dataclass(slots=True)
class FinishedSession:
    """O que sobra de uma gravação encerrada.

    Os contadores viajam junto com os registros porque a sessão é descartada em
    seguida: pedir `status()` depois do `finish()` devolveria o gravador ocioso,
    e `dedup_skipped` — o número que explica por que 500 amostras viraram 180
    arquivos — se perderia calado.
    """

    version: str
    records: list[dict[str, Any]] = field(default_factory=list)
    saved: int = 0
    bytes: int = 0
    dedup_skipped: int = 0
    stale_skipped: int = 0
    io_dropped: int = 0
    write_errors: int = 0
    error: str | None = None


@dataclass(slots=True)
class RecorderStatus:
    """O que a tela mostra durante a gravação.

    `dedup_skipped` não é enfeite: sem ele o operador conta 500 quadros
    amostrados, encontra 180 arquivos e passa a tarde procurando o erro.
    """

    active: bool = False
    status: CollectionStatus | None = None
    version: str | None = None
    saved: int = 0
    bytes: int = 0
    elapsed_seconds: float = 0.0
    dedup_skipped: int = 0
    stale_skipped: int = 0
    io_dropped: int = 0
    write_errors: int = 0
    last_file: str | None = None
    paused_reason: str | None = None
    error: str | None = None
    queue_depth: int = 0
    disk_percent: float = 0.0
    disk_free_bytes: int = 0
    disk_over_limit: bool = False


@dataclass(slots=True)
class _Session:
    """Tudo que se sabe sobre uma gravação enquanto ela acontece."""

    version: str
    base: Path
    interval: float
    limit: int | None
    dedup: bool

    started_epoch: float = field(default_factory=time.time)
    ended_epoch: float | None = None
    t0: float | None = None
    next_index: int = 1
    records: list[dict[str, Any]] = field(default_factory=list)
    bytes: int = 0
    saved: int = 0
    dedup_skipped: int = 0
    stale_skipped: int = 0
    io_dropped: int = 0
    write_errors: int = 0
    last_file: str | None = None
    last_seq: int = 0
    last_gray: Any = None
    paused_reason: str | None = None
    error: str | None = None

    @property
    def raw(self) -> Path:
        return self.base / storage.RAW_DIR

    def document(self, state: str) -> dict[str, Any]:
        return {
            "version": self.version,
            "status": state,
            "started_at": self.started_epoch,
            "ended_at": self.ended_epoch,
            "duration_s": round((self.ended_epoch or time.time()) - self.started_epoch, 2),
            "params": {
                "interval_s": self.interval,
                "limit": self.limit,
                "dedup": self.dedup,
                "dedup_threshold": settings.dedup_threshold if self.dedup else None,
                "jpeg_quality": settings.collect_jpeg_quality,
            },
            "time_base": (
                "t = frame.captured_at menos o captured_at do primeiro quadro salvo "
                "(relógio monotônico do leitor, imune a reconexão do RTSP)"
            ),
            "counts": {
                "saved": self.saved,
                "dedup_skipped": self.dedup_skipped,
                "stale_skipped": self.stale_skipped,
                "io_dropped": self.io_dropped,
                "write_errors": self.write_errors,
            },
            "bytes": self.bytes,
            "paused_reason": self.paused_reason,
            "error": self.error,
            "frames": self.records,
        }

    def flush(self, state: str) -> None:
        """Grava `session.json` de forma atômica.

        tmp + `os.replace`: uma queda no meio da escrita deixa o arquivo
        anterior intacto, nunca um JSON truncado. E mesmo perdendo o último
        flush o dataset continua íntegro — o nome de cada arquivo em `raw/`
        carrega o índice e o tempo, que é tudo que o split precisa.
        """
        path = self.base / storage.SESSION_NAME
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(
                json.dumps(self.document(state), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp, path)
        except OSError as exc:
            self.error = f"falha ao gravar session.json: {exc}"[:200]


class CollectionRecorder:
    """Uma gravação por processo. Instância única, como o leitor de vídeo."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: CollectionStatus | None = None
        self._session: _Session | None = None
        self._token: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(
            maxsize=settings.collect_queue_max
        )
        self._writers: list[threading.Thread] = []
        self._sampler: threading.Thread | None = None
        self._stop = threading.Event()

    # --- estado ---------------------------------------------------------------

    @property
    def active(self) -> bool:
        with self._lock:
            return self._state in (CollectionStatus.RECORDING, CollectionStatus.PAUSED)

    @property
    def version(self) -> str | None:
        with self._lock:
            return self._session.version if self._session else None

    def status(self) -> RecorderStatus:
        with self._lock:
            state = self._state
            session = self._session
        disk = storage.disk_usage()
        base = RecorderStatus(
            queue_depth=self._queue.qsize(),
            disk_percent=disk.percent,
            disk_free_bytes=disk.free_bytes,
            disk_over_limit=disk.over_limit,
        )
        if session is None or state is None:
            return base

        base.active = state in (CollectionStatus.RECORDING, CollectionStatus.PAUSED)
        base.status = state
        base.version = session.version
        base.saved = session.saved
        base.bytes = session.bytes
        base.elapsed_seconds = round(
            (session.ended_epoch or time.time()) - session.started_epoch, 1
        )
        base.dedup_skipped = session.dedup_skipped
        base.stale_skipped = session.stale_skipped
        base.io_dropped = session.io_dropped
        base.write_errors = session.write_errors
        base.last_file = session.last_file
        base.paused_reason = session.paused_reason
        base.error = session.error
        return base

    # --- transições -----------------------------------------------------------

    def start(self, version: str, base: Path, interval: float, limit: int | None, dedup: bool) -> None:
        with self._lock:
            if self.active:
                raise RuntimeError(f"já existe uma coleta em andamento ({self.version})")

            self._loop = _running_loop()
            session = _Session(
                version=version, base=base, interval=interval, limit=limit, dedup=dedup
            )
            self._session = session
            self._state = CollectionStatus.RECORDING

            # A coleta é consumidora do vídeo: durante a gravação pode não haver
            # navegador nenhum aberto, e o leitor tem que continuar mesmo assim.
            self._token = video.consumers.add("collect", version)
            video.start()

            self._drain_queue()
            self._start_writers()
            self._stop.clear()
            self._sampler = threading.Thread(
                target=self._sample_loop, name="collect-sampler", daemon=True
            )
            self._sampler.start()
            session.flush(CollectionStatus.RECORDING)
            log.info("collect_started", version=version, interval=interval, limit=limit)

    def pause(self, reason: str | None = None) -> None:
        with self._lock:
            if self._state != CollectionStatus.RECORDING or self._session is None:
                return
            self._state = CollectionStatus.PAUSED
            self._session.paused_reason = reason
            self._session.flush(CollectionStatus.PAUSED)
        log.info("collect_paused", version=self.version, reason=reason)

    def resume(self) -> None:
        with self._lock:
            if self._state != CollectionStatus.PAUSED or self._session is None:
                return
            session = self._session
            if session.limit is not None and (session.next_index - 1) >= session.limit:
                # A pausa foi do limite, e o operador clicou em Continuar mesmo
                # assim: isso é uma decisão de ignorá-lo. Mantê-lo faria a
                # amostradora gravar um quadro e pausar de novo, a cada clique
                # — a tela pareceria travada sem nada errado acontecendo.
                log.info(
                    "collect_limite_dispensado", version=session.version, limit=session.limit
                )
                session.limit = None
            self._state = CollectionStatus.RECORDING
            session.paused_reason = None
            session.flush(CollectionStatus.RECORDING)

    def finish(self) -> FinishedSession | None:
        """Encerra a gravação e devolve o que foi gravado.

        A ordem importa. Parar a amostradora antes da barreira da fila garante
        que nenhum quadro novo entra; esperar a fila esvaziar antes de listar
        `raw/` garante que nenhum arquivo ainda em voo saia calado do manifesto.
        """
        with self._lock:
            session = self._session
            if session is None:
                return None
            session.ended_epoch = time.time()

        self._stop.set()
        if self._sampler:
            self._sampler.join(timeout=10)
            self._sampler = None

        self._queue.join()
        self._stop_writers()

        with self._lock:
            session.flush(CollectionStatus.SAVED)
            finished = FinishedSession(
                version=session.version,
                records=list(session.records),
                saved=session.saved,
                bytes=session.bytes,
                dedup_skipped=session.dedup_skipped,
                stale_skipped=session.stale_skipped,
                io_dropped=session.io_dropped,
                write_errors=session.write_errors,
                error=session.error,
            )
            self._release_consumer()
            self._state = None
            self._session = None
        log.info("collect_finished", version=finished.version, saved=finished.saved)
        return finished

    def abort(self) -> None:
        """Interrompe sem particionar. Os arquivos já gravados ficam em `raw/`."""
        with self._lock:
            session = self._session
        if session is None:
            return
        self._stop.set()
        if self._sampler:
            self._sampler.join(timeout=10)
            self._sampler = None
        self._drain_queue()
        self._stop_writers()
        with self._lock:
            session.ended_epoch = time.time()
            session.flush(CollectionStatus.CANCELLED)
            self._release_consumer()
            self._state = None
            self._session = None

    def shutdown(self) -> None:
        """Encerra o processo sem perder o que já está em disco."""
        with self._lock:
            session = self._session
            state = self._state
        if session is None:
            return
        self._stop.set()
        if self._sampler:
            self._sampler.join(timeout=5)
        if self._writers:
            self._queue.join()
            self._stop_writers()
        with self._lock:
            session.flush(state or CollectionStatus.PAUSED)

    def _release_consumer(self) -> None:
        if self._token is not None:
            video.consumers.discard(self._token)
            self._token = None

    # --- amostragem -----------------------------------------------------------

    def _sample_loop(self) -> None:
        session = self._session
        if session is None:
            return
        now = time.monotonic()
        next_sample = now
        next_disk = now + DISK_CHECK_EVERY_S
        next_flush = now + SESSION_FLUSH_EVERY_S

        while not self._stop.is_set():
            now = time.monotonic()

            if now >= next_disk:
                usage = storage.disk_usage()
                if usage.over_limit and self._state == CollectionStatus.RECORDING:
                    reason = (
                        f"disco em {usage.percent:.0f}% (limite {usage.limit_pct:.0f}%) — "
                        "coleta interrompida. Libere espaço e clique em Continuar."
                    )
                    self.pause(reason)
                    self._announce("collection.paused", reason=reason, automatic=True)
                next_disk = now + DISK_CHECK_EVERY_S

            if self._state == CollectionStatus.RECORDING and now >= next_sample:
                self._sample_once(session)
                next_sample += session.interval
                if next_sample < now:  # atraso maior que um intervalo: ressincroniza
                    next_sample = now + session.interval

            if now >= next_flush:
                with self._lock:
                    if self._session is session:
                        session.flush(self._state or CollectionStatus.PAUSED)
                next_flush = now + SESSION_FLUSH_EVERY_S

            self._stop.wait(TICK_S)

    def _sample_once(self, session: _Session) -> None:
        import cv2

        frame = video.raw_frame()
        if frame is None or frame.seq == session.last_seq:
            # Sem quadro novo: leitor ocioso, RTSP caído ou reconectando. A
            # sessão continua aberta e volta a gravar sozinha quando o vídeo
            # voltar — é o que a mantém consistente numa queda do MediaMTX.
            session.stale_skipped += 1
            return

        session.last_seq = frame.seq
        image = frame.image
        gray = None

        if session.dedup:
            gray = cv2.resize(
                cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),
                (DEDUP_SIZE, DEDUP_SIZE),
                interpolation=cv2.INTER_AREA,
            )
            if session.last_gray is not None:
                # Comparado com o último quadro SALVO, não com o último lido:
                # contra o anterior lido, uma deriva lenta passaria quadro a
                # quadro e o dataset encheria de quase-duplicatas mesmo assim.
                mad = float(cv2.absdiff(gray, session.last_gray).mean())
                if mad < settings.dedup_threshold:
                    session.dedup_skipped += 1
                    return

        if session.t0 is None:
            session.t0 = frame.captured_at
        seconds = frame.captured_at - session.t0

        index = session.next_index
        name = f"{index:06d}_t{seconds:.2f}.jpg"
        job = {
            "session": session,
            "path": session.raw / name,
            "image": image,
            "record": {
                "index": index,
                "file": name,
                "t": round(seconds, 2),
                "epoch": frame.captured_epoch,
                "seq": frame.seq,
                "width": frame.size[0],
                "height": frame.size[1],
            },
        }
        try:
            self._queue.put_nowait(job)
        except queue.Full:
            # A escrita não acompanha a amostragem. Descartar aqui é a decisão
            # correta: bloquear seguraria a amostradora, e enfileirar faria a
            # memória crescer sem teto — cada item é um quadro decodificado.
            session.io_dropped += 1
            return

        session.next_index += 1
        if gray is not None:
            session.last_gray = gray

        # Conta pelo que foi aceito para escrita, não por `saved`: `saved` é
        # incrementado pelos workers e chegaria atrasado ao limite.
        if session.limit is not None and (session.next_index - 1) >= session.limit:
            # Auto-pausa, não auto-salva: salvar dispara o split, e essa decisão
            # é do operador. A sessão fica aberta e pode continuar se ele quiser.
            reason = f"limite de {session.limit} quadros atingido"
            self.pause(reason)
            self._announce("collection.paused", reason=reason, automatic=True)

    # --- escrita --------------------------------------------------------------

    def _start_writers(self) -> None:
        self._writers = []
        for index in range(settings.collect_writers):
            thread = threading.Thread(
                target=self._writer_loop, name=f"collect-writer-{index}", daemon=True
            )
            thread.start()
            self._writers.append(thread)

    def _writer_loop(self) -> None:
        try:
            # No Linux o nice() vale para a thread que chama, não para o
            # processo: só os workers de escrita cedem CPU, o leitor e o encode
            # do MJPEG não.
            os.nice(settings.collect_writer_nice)
        except OSError:  # pragma: no cover — depende da política do host
            pass

        while True:
            job = self._queue.get()
            try:
                if job is None:
                    return
                self._write(job)
            finally:
                self._queue.task_done()

    @staticmethod
    def _write(job: dict[str, Any]) -> None:
        import cv2

        session: _Session = job["session"]
        try:
            ok, buffer = cv2.imencode(
                ".jpg", job["image"], [int(cv2.IMWRITE_JPEG_QUALITY), settings.collect_jpeg_quality]
            )
            if not ok:
                raise OSError("imencode falhou")
            data = buffer.tobytes()
            tmp = job["path"].with_suffix(".jpg.tmp")
            tmp.write_bytes(data)
            os.replace(tmp, job["path"])
        except (OSError, cv2.error) as exc:
            session.write_errors += 1
            session.error = f"falha ao gravar quadro: {exc}"[:200]
            return

        record = {**job["record"], "bytes": len(data)}
        session.records.append(record)
        session.saved += 1
        session.bytes += len(data)
        session.last_file = record["file"]

    def _drain_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return
            self._queue.task_done()

    def _stop_writers(self) -> None:
        for _ in self._writers:
            self._queue.put(None)
        for thread in self._writers:
            thread.join(timeout=10)
        self._writers = []

    # --- aviso ao frontend ----------------------------------------------------

    def _announce(self, event: str, **payload: Any) -> None:
        """Publica no barramento SSE a partir de uma thread.

        Auto-pausa por disco ou por limite acontece sem ninguém clicar em nada.
        Sem este empurrão a tela só descobriria na próxima revalidação, e o
        operador ficaria olhando "Gravando" com a gravação parada.
        """
        from app.core.events import bus

        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(bus.publish(event, **payload), loop)
        except RuntimeError:  # pragma: no cover — laço encerrando
            pass


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


recorder = CollectionRecorder()
"""Instância única do processo."""
