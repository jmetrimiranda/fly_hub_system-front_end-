"""Versionamento, nomes de arquivo e as barreiras de caminho.

O versionamento é varrido do disco de propósito — um contador no banco volta a
`v0.0` quando alguém apaga uma linha, e a coleta seguinte passa a escrever
dentro de uma pasta que já tem quadros.
"""

import pytest

from app.core.errors import NotFoundError
from app.services import dataset_storage as storage


@pytest.fixture
def datasets_dir(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "datasets_dir", tmp_path)
    return tmp_path


def test_the_first_version_is_v0_0(datasets_dir):
    assert storage.next_version() == "v0.0"


def test_the_minor_rolls_into_the_next_major(datasets_dir):
    for name in ("v0.0", "v0.7", "v0.9"):
        (datasets_dir / name).mkdir()
    assert storage.next_version() == "v1.0"


def test_a_folder_created_by_hand_enters_the_sequence(datasets_dir):
    (datasets_dir / "v3.4").mkdir()
    (datasets_dir / "coisa-qualquer").mkdir()  # fora do padrão: ignorada
    assert storage.next_version() == "v3.5"


def test_the_frame_name_carries_index_and_time():
    assert storage.parse_frame_name("000123_t45.50.jpg") == (123, 45.5)
    assert storage.parse_frame_name("captura.jpg") is None


def test_raw_is_listed_in_temporal_order(datasets_dir):
    base = storage.create_version("v0.0")
    for name in ("000002_t2.00.jpg", "000010_t20.00.jpg", "000001_t0.00.jpg", "leiame.txt"):
        (base / storage.RAW_DIR / name).write_bytes(b"x")

    frames, ignored = storage.list_raw(base)
    assert [frame.index for frame in frames] == [1, 2, 10]
    assert ignored == ["leiame.txt"]


def test_a_filename_from_the_url_never_becomes_a_path(datasets_dir):
    """Travessia de diretório é recusada antes de virar caminho."""
    base = storage.create_version("v0.0")
    for attempt in ("../../etc/passwd", "sub/dir.jpg", ".oculto.jpg"):
        with pytest.raises(NotFoundError):
            storage.image_path(base, None, attempt)


def test_a_version_taken_only_in_the_database_is_skipped(datasets_dir):
    """A pasta apagada à mão não libera o número.

    `datasets.version` é único. Sem esta consulta, a coleta seguinte tentaria
    gravar em `v0.0` e morreria numa violação de chave — um 500 sem explicação
    para quem só clicou em coletar.
    """
    assert storage.next_version(["v0.0", "v0.1"]) == "v0.2"


def test_disk_and_database_are_considered_together(datasets_dir):
    (datasets_dir / "v0.5").mkdir()
    assert storage.next_version(["v0.9"]) == "v1.0"
