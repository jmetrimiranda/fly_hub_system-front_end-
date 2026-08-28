"""O dataset como ele existe em disco: versões, pastas, arquivos, miniaturas.

Portado de `app/datasets.py` do M4TD. Aqui ficam só operações de sistema de
arquivos — nada de banco, nada de HTTP. É o vocabulário que
`collection_service`, `split_runner` e `dataset_service` compartilham.

Por que o disco manda no versionamento
--------------------------------------
`next_version()` varre `DATASETS_DIR`; não existe contador em memória nem no
banco. Uma pasta criada à mão entra na sequência, um processo reiniciado não
repete uma versão, e um banco recriado do zero não sobrescreve coleta antiga.
Um contador (`count(datasets) // 10`, que é o que esta plataforma fazia antes)
volta a `v0.0` assim que alguém apaga uma linha — e a coleta seguinte escreve
dentro de uma pasta que já tem quadros.

Layout de uma versão::

    data/datasets/v0.3/
    ├── raw/                    quadros originais, como saíram do leitor
    │   ├── 000001_t0.00.jpg
    │   └── 000002_t2.00.jpg
    ├── train/images/           cópias, decididas pelo split
    ├── valid/images/
    ├── test/images/
    ├── .thumbs/                cache de miniaturas, derivado
    ├── session.json            como a gravação aconteceu
    └── split_manifest.json     o que o split decidiu

`raw/` é **mantido** depois do split: é o que permite refazer a partição depois
que o operador exclui imagens.

O tempo no nome do arquivo
--------------------------
`000123_t45.50.jpg` — o índice zero-preenchido faz a ordem lexicográfica ser a
ordem temporal, e o `t` é o tempo relativo ao primeiro quadro salvo. Juntos,
permitem particionar e auditar as fronteiras sem reabrir o banco.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.errors import NotFoundError, SplitError

SPLITS = ("train", "valid", "test")
RAW_DIR = "raw"
SESSION_NAME = "session.json"
MANIFEST_NAME = "split_manifest.json"

# Ponto no início para não aparecer em listagem e não confundir o split, que
# ignora nomes começados por ponto.
THUMBS_DIR = ".thumbs"
THUMB_WIDTH = 240
THUMB_QUALITY = 72

VERSION_RE = re.compile(r"^v(\d+)\.(\d)$")
MAX_MINOR = 9

FRAME_RE = re.compile(r"^(\d+)_t(-?\d+\.\d+)\.jpg$")


@dataclass(frozen=True, slots=True)
class RawFrame:
    """Um arquivo de `raw/` com o que o nome dele carrega."""

    filename: str
    index: int
    seconds: float
    """Tempo relativo ao primeiro quadro salvo da sessão."""


@dataclass(frozen=True, slots=True)
class DiskUsage:
    ok: bool
    percent: float = 0.0
    free_bytes: int = 0
    total_bytes: int = 0
    limit_pct: float = 0.0
    over_limit: bool = False
    error: str | None = None


# --- versões -----------------------------------------------------------------


def parse_version(name: str) -> tuple[int, int] | None:
    match = VERSION_RE.match(name)
    return (int(match.group(1)), int(match.group(2))) if match else None


def format_version(major: int, minor: int) -> str:
    return f"v{major}.{minor}"


def existing_versions() -> list[tuple[int, int]]:
    """Versões presentes em disco, ordenadas. Só diretório com nome válido."""
    try:
        entries = list(settings.datasets_dir.iterdir())
    except OSError:
        return []
    found = [parse_version(entry.name) for entry in entries if entry.is_dir()]
    return sorted(item for item in found if item is not None)


def _bump(major: int, minor: int) -> tuple[int, int]:
    """`v0.9 → v1.0`. O MINOR vai de 0 a 9 e rola para o próximo MAJOR."""
    return (major + 1, 0) if minor >= MAX_MINOR else (major, minor + 1)


def next_version(taken: Iterable[str] = ()) -> str:
    """A próxima versão livre. Primeira execução devolve `v0.0`.

    `taken` recebe as versões que o **banco** já conhece. O disco manda no
    versionamento, mas a coluna `datasets.version` é única: uma linha cuja pasta
    foi apagada à mão continua ocupando o número, e sem esta lista a coleta
    seguinte tentaria gravar nele e morreria numa violação de chave — um 500 sem
    explicação nenhuma para quem só clicou em coletar.

    O laço final também não é zelo excessivo: `existing_versions()` ignora nomes
    fora do padrão, e um diretório criado entre a varredura e a criação faria a
    coleta escrever dentro de um dataset alheio.
    """
    reserved = {name for name in taken if parse_version(name)}
    parsed = existing_versions() + [item for item in map(parse_version, reserved) if item]
    candidate = _bump(*sorted(parsed)[-1]) if parsed else (0, 0)
    while (
        version_dir(format_version(*candidate)).exists()
        or format_version(*candidate) in reserved
    ):
        candidate = _bump(*candidate)
    return format_version(*candidate)


def version_dir(version: str) -> Path:
    return settings.datasets_dir / version


def create_version(version: str) -> Path:
    """Cria `<versão>/raw/`. Falha se a versão já existir."""
    base = version_dir(version)
    (base / RAW_DIR).mkdir(parents=True, exist_ok=False)
    return base


def require_version(version: str) -> Path:
    base = version_dir(version)
    if not base.is_dir():
        raise NotFoundError(f"O dataset {version} não existe em disco.")
    return base


# --- disco -------------------------------------------------------------------


def _existing_ancestor(path: Path) -> Path:
    """`disk_usage` exige caminho existente; `data/datasets/` pode não existir."""
    current = path.resolve()
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def disk_usage() -> DiskUsage:
    limit = settings.disk_limit_pct
    try:
        usage = shutil.disk_usage(_existing_ancestor(settings.datasets_dir))
    except OSError as exc:
        return DiskUsage(ok=False, limit_pct=limit, error=str(exc))

    percent = usage.used / usage.total * 100 if usage.total else 0.0
    return DiskUsage(
        ok=True,
        percent=round(percent, 1),
        free_bytes=usage.free,
        total_bytes=usage.total,
        limit_pct=limit,
        over_limit=percent >= limit,
    )


def dir_size(path: Path, skip: tuple[str, ...] = (THUMBS_DIR,)) -> int:
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [name for name in dirs if name not in skip]
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


# --- arquivos ----------------------------------------------------------------


def parse_frame_name(name: str) -> tuple[int, float] | None:
    match = FRAME_RE.match(name)
    return (int(match.group(1)), float(match.group(2))) if match else None


def list_raw(base: Path) -> tuple[list[RawFrame], list[str]]:
    """Quadros de `raw/` em ordem temporal, mais os nomes que não casaram."""
    raw = base / RAW_DIR
    if not raw.is_dir():
        raise SplitError(f"{raw} não existe — não há quadros para particionar.")

    frames: list[RawFrame] = []
    ignored: list[str] = []
    for entry in sorted(os.listdir(raw)):
        parsed = parse_frame_name(entry)
        if parsed is None:
            if not entry.startswith("."):
                ignored.append(entry)
            continue
        frames.append(RawFrame(filename=entry, index=parsed[0], seconds=parsed[1]))

    frames.sort(key=lambda frame: (frame.index, frame.seconds))
    return frames, ignored


def split_dir(base: Path, split: str) -> Path:
    return base / require_split(split) / "images"


def require_split(split: str) -> str:
    if split not in SPLITS:
        raise NotFoundError(f"Partição desconhecida: {split!r}. Use train, valid ou test.")
    return split


def split_files(base: Path, split: str) -> list[str]:
    target = split_dir(base, split)
    try:
        return sorted(
            entry.name
            for entry in os.scandir(target)
            if entry.is_file() and not entry.name.startswith(".")
        )
    except OSError:
        return []


def raw_files(base: Path) -> list[str]:
    try:
        return sorted(
            entry.name
            for entry in os.scandir(base / RAW_DIR)
            if entry.is_file() and not entry.name.startswith(".")
        )
    except OSError:
        return []


def live_counts(base: Path) -> dict[str, int]:
    """Contagem **do disco**, contada na hora.

    O manifesto registra o que o split decidiu; excluir imagem depois não o
    reescreve. Divergir do manifesto é normal e é exibido, não escondido.
    """
    counts = {name: len(split_files(base, name)) for name in SPLITS}
    counts["raw"] = len(raw_files(base))
    counts["total"] = sum(counts[name] for name in SPLITS)
    return counts


def reset_split_dirs(base: Path) -> None:
    """Zera train|valid|test. Sem isto, um resplit deixaria órfãos do anterior."""
    for name in SPLITS:
        target = base / name
        if target.exists():
            shutil.rmtree(target)
        (target / "images").mkdir(parents=True, exist_ok=True)
    # As miniaturas são indexadas por partição, e o resplit move os arquivos
    # entre partições: o cache inteiro deixa de valer.
    shutil.rmtree(base / THUMBS_DIR, ignore_errors=True)


def safe_name(filename: str) -> str:
    """Recusa qualquer nome que não seja um arquivo direto da pasta.

    O nome chega pela URL ou pelo corpo da requisição. Sem esta barreira,
    `../../../etc/passwd` viraria caminho.
    """
    if filename != Path(filename).name or filename.startswith(".") or not filename:
        raise NotFoundError(f"Nome de arquivo inválido: {filename!r}")
    return filename


def image_path(base: Path, split: str | None, filename: str) -> Path:
    """Caminho de uma imagem, validado contra travessia de diretório.

    `split=None` lê de `raw/` — é o que a galeria usa para um dataset ainda não
    particionado.
    """
    safe_name(filename)
    folder = split_dir(base, split) if split else base / RAW_DIR
    path = folder / filename
    # Defesa final: o arquivo resolvido tem que estar mesmo dentro da pasta.
    if not path.is_file() or path.resolve().parent != folder.resolve():
        raise NotFoundError(f"{filename} não existe em {base.name}/{split or RAW_DIR}.")
    return path


def thumb_path(base: Path, split: str | None, filename: str) -> Path:
    """Miniatura, gerada sob demanda e cacheada em disco.

    Mandar o JPEG inteiro quinhentas vezes para montar uma grade desperdiça
    banda e memória do navegador; gerar a miniatura a cada requisição
    desperdiça CPU. O cache resolve os dois, e é invalidado por mtime.
    """
    import cv2

    source = image_path(base, split, filename)
    cache = base / THUMBS_DIR / (split or RAW_DIR) / filename
    try:
        if cache.is_file() and cache.stat().st_mtime >= source.stat().st_mtime:
            return cache
    except OSError:
        pass

    image = cv2.imread(str(source))
    if image is None:
        raise NotFoundError(f"Não foi possível ler {filename}.")
    height, width = image.shape[:2]
    if width > THUMB_WIDTH:
        scale = THUMB_WIDTH / width
        image = cv2.resize(
            image, (THUMB_WIDTH, max(int(height * scale), 1)), interpolation=cv2.INTER_AREA
        )
    # imencode + write, não imwrite: o imwrite escolhe o codec pela extensão do
    # caminho, e o arquivo temporário termina em `.tmp`.
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), THUMB_QUALITY])
    if not ok:
        raise NotFoundError(f"Não foi possível gerar a miniatura de {filename}.")
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + ".tmp")
    tmp.write_bytes(buffer.tobytes())
    os.replace(tmp, cache)
    return cache


def delete_image_files(base: Path, split: str | None, filename: str) -> bool:
    """Apaga da partição **e** de `raw/`. Devolve se algo foi mesmo removido.

    Apagar só da partição faria o "refazer o split a partir de `raw/`" — que é
    oferecido justamente porque as proporções mudaram — ressuscitar todas as
    imagens excluídas.
    """
    safe_name(filename)
    removed = False
    for candidate in filter(
        None,
        (
            (split_dir(base, split) / filename) if split else None,
            base / RAW_DIR / filename,
        ),
    ):
        try:
            candidate.unlink()
            removed = True
        except OSError:
            continue

    # A miniatura é derivada: some junto, e sua ausência não conta como remoção.
    try:
        (base / THUMBS_DIR / (split or RAW_DIR) / filename).unlink()
    except OSError:
        pass
    return removed


def delete_version(base: Path) -> int:
    """Apaga a versão inteira. Devolve os bytes liberados."""
    size = dir_size(base)
    shutil.rmtree(base)
    return size
