"""Aplica o split temporal em disco e grava o manifesto.

Divisão de responsabilidade
---------------------------
* `splitting.assign_temporal_splits` **decide**. É pura, recebe timestamps e
  devolve rótulos, e é onde mora a regra do ADR 004.
* Este módulo **executa**: lê `raw/`, chama a decisão, copia os arquivos para
  `train|valid|test/images/` e escreve `split_manifest.json`.

Copia, não move. `raw/` fica intacto — é o que permite refazer o split depois
que o operador exclui imagens da galeria, e é o único caminho de volta se a
proporção sair ruim.

O tempo vem do nome do arquivo, não do banco. `000123_t45.50.jpg` carrega o
índice e o instante relativo, então particionar (e reparticionar) não depende
de nenhuma linha estar gravada. Um dataset copiado para outra máquina continua
particionável.

Roda em uma thread só, sem paralelismo: acontece depois do Salvar, quando o
operador já não depende do vídeo em tempo real, e não vale disputar CPU com o
encode do MJPEG por alguns segundos de cópia.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import SplitError
from app.core.logging import get_logger
from app.services import dataset_storage as storage
from app.services.dataset_storage import MANIFEST_NAME, RAW_DIR, SPLITS, RawFrame
from app.services.splitting import (
    STRATEGY,
    STRATEGY_REASON,
    SplitConfig,
    SplitResult,
    SplitWarning,
    assign_temporal_splits,
)

log = get_logger(__name__)

# Instante arbitrário: `assign_temporal_splits` só usa diferenças entre os
# timestamps, e o `t` do nome do arquivo é relativo ao primeiro quadro salvo.
_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


def config_from_settings() -> SplitConfig:
    return SplitConfig(
        train_ratio=settings.split_train_ratio,
        valid_ratio=settings.split_valid_ratio,
        test_ratio=settings.split_test_ratio,
        embargo_seconds=settings.split_embargo_seconds,
        embargo_frames=settings.split_embargo_frames,
    )


def decide(frames: list[RawFrame], config: SplitConfig | None = None) -> SplitResult:
    """Rótulos para os quadros de `raw/`, na ordem em que foram passados."""
    stamps = [_EPOCH + timedelta(seconds=frame.seconds) for frame in frames]
    return assign_temporal_splits(stamps, config or config_from_settings())


def _write_manifest(base: Path, manifest: dict[str, Any]) -> Path:
    """Escrita atômica: uma queda no meio deixa o manifesto anterior intacto."""
    path = base / MANIFEST_NAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def read_manifest(base: Path) -> dict[str, Any] | None:
    try:
        return json.loads((base / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run(
    base: Path,
    config: SplitConfig | None = None,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Particiona `base/raw/` e grava o manifesto. Devolve o manifesto.

    Sem manifesto não há como reproduzir nem auditar o experimento: ele é a
    única resposta para "por que este quadro está em valid" seis meses depois.
    """
    config = config or config_from_settings()
    frames, ignored = storage.list_raw(base)
    if not frames:
        raise SplitError(
            f"Nenhum quadro em {base.name}/{RAW_DIR}/ — não há o que particionar."
        )

    result = decide(frames, config)
    storage.reset_split_dirs(base)

    copied: dict[str, list[dict[str, Any]]] = {name: [] for name in SPLITS}
    discarded: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for frame, assignment in zip(frames, result.assignments, strict=True):
        record = {"file": frame.filename, "index": frame.index, "t": frame.seconds}
        if assignment.split is None:
            discarded.append({**record, "reason": "faixa de embargo entre partições"})
            continue
        target = storage.split_dir(base, assignment.split)
        try:
            shutil.copy2(base / RAW_DIR / frame.filename, target / frame.filename)
        except OSError as exc:
            errors.append({"file": frame.filename, "split": str(assignment.split), "error": str(exc)})
            continue
        copied[str(assignment.split)].append(record)

    warnings = [_warning(item) for item in result.warnings]
    if ignored:
        warnings.append(
            _warning(
                SplitWarning(
                    "arquivos_ignorados",
                    "warn",
                    f"{len(ignored)} arquivo(s) em {RAW_DIR}/ fora do padrão "
                    "`NNNNNN_tSS.SS.jpg` foram ignorados: "
                    + ", ".join(ignored[:5])
                    + ("…" if len(ignored) > 5 else ""),
                )
            )
        )
    if errors:
        warnings.append(
            _warning(
                SplitWarning(
                    "falha_ao_copiar",
                    "error",
                    f"{len(errors)} quadro(s) não puderam ser copiados para as partições.",
                )
            )
        )

    times = [frame.seconds for frame in frames]
    manifest = {
        "version": base.name,
        "created_at": datetime.now(UTC).isoformat(),
        "strategy": STRATEGY,
        "reason": STRATEGY_REASON,
        "source": RAW_DIR,
        "ratios": {
            "train": config.train_ratio,
            "valid": config.valid_ratio,
            "test": config.test_ratio,
        },
        "embargo": {
            "seconds_requested": config.embargo_seconds,
            "seconds": result.embargo_seconds_applied,
            "frames_requested": config.embargo_frames,
            "frames_applied": result.embargo_frames_applied,
        },
        "total_raw": len(frames),
        "counts": {
            **{name: len(copied[name]) for name in SPLITS},
            "embargoed": len(discarded),
            "kept": sum(len(copied[name]) for name in SPLITS),
        },
        "time_span": {
            "first_t": times[0],
            "last_t": times[-1],
            "duration_s": round(times[-1] - times[0], 2) if len(times) > 1 else 0.0,
        },
        "warnings": warnings,
        "copy_errors": errors,
        "session": session,
        "files": {**copied, "embargoed": discarded},
    }
    _write_manifest(base, manifest)
    log.info(
        "split_applied",
        version=base.name,
        total=len(frames),
        **{name: len(copied[name]) for name in SPLITS},
        embargoed=len(discarded),
    )
    return manifest


def _warning(item: SplitWarning) -> dict[str, str]:
    return {"code": item.code, "level": item.level, "message": item.message}
