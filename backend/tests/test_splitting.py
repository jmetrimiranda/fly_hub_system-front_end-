"""O split temporal é a regra mais fácil de errar em silêncio — por isso testes.

`SplitConfig` tem duas unidades de embargo, e os testes que medem proporção
exata zeram as duas de propósito: sem `embargo_frames=0` a margem em quadros
continua descartando cinco de cada lado dos cortes, e a contagem "exata" nunca
fecha. Os testes que medem a *propriedade* — vizinho não atravessa fronteira —
usam a configuração de verdade.
"""

from datetime import UTC, datetime, timedelta

from app.models.enums import SplitName
from app.services.splitting import SplitConfig, assign_temporal_splits

START = datetime(2026, 8, 26, 14, 0, tzinfo=UTC)

NO_EMBARGO = SplitConfig(embargo_seconds=0, embargo_frames=0)


def _frames(count: int, step_ms: int = 33) -> list[datetime]:
    return [START + timedelta(milliseconds=step_ms * i) for i in range(count)]


def test_empty_input_returns_empty_result():
    result = assign_temporal_splits([])
    assert result.assignments == []
    assert (result.train, result.valid, result.test) == (0, 0, 0)


def test_train_comes_before_valid_which_comes_before_test():
    stamps = _frames(1000, step_ms=1000)
    result = assign_temporal_splits(stamps, NO_EMBARGO)

    by_split: dict[SplitName, list[datetime]] = {}
    for assignment in result.assignments:
        if assignment.split:
            by_split.setdefault(assignment.split, []).append(stamps[assignment.index])

    assert max(by_split[SplitName.TRAIN]) < min(by_split[SplitName.VALID])
    assert max(by_split[SplitName.VALID]) < min(by_split[SplitName.TEST])


def test_embargo_removes_frames_around_the_boundaries():
    stamps = _frames(600, step_ms=1000)
    without = assign_temporal_splits(stamps, NO_EMBARGO)
    with_embargo = assign_temporal_splits(stamps, SplitConfig(embargo_seconds=10))

    assert without.embargoed == 0
    assert with_embargo.embargoed > 0
    assert with_embargo.train + with_embargo.valid + with_embargo.test < len(stamps)


def test_ratios_are_respected_within_rounding():
    stamps = _frames(1000, step_ms=1000)
    result = assign_temporal_splits(
        stamps, SplitConfig(0.8, 0.1, 0.1, embargo_seconds=0, embargo_frames=0)
    )
    assert result.train == 800
    assert abs(result.valid - 100) <= 1
    assert abs(result.test - 100) <= 1


def test_input_order_is_preserved_in_the_output():
    stamps = list(reversed(_frames(50, step_ms=1000)))
    result = assign_temporal_splits(stamps, NO_EMBARGO)
    assert [a.index for a in result.assignments] == list(range(50))
    # O primeiro item da lista é o mais recente, logo deve cair em test.
    assert result.assignments[0].split == SplitName.TEST


def test_ratios_must_sum_to_one():
    import pytest

    with pytest.raises(ValueError, match="1.0"):
        SplitConfig(0.5, 0.5, 0.5)


def test_adjacent_frames_never_land_in_different_partitions():
    """A propriedade que dá sentido ao embargo.

    Sem margem, o quadro N em train e o N+1 em valid é vazamento: as duas
    imagens são a mesma cena deslocada por um intervalo de amostragem. Com
    margem, todo par de vizinhos temporais ou está na mesma partição, ou pelo
    menos um dos dois foi descartado.
    """
    stamps = _frames(400, step_ms=2000)
    result = assign_temporal_splits(stamps)
    labels = [assignment.split for assignment in result.assignments]

    for before, after in zip(labels, labels[1:], strict=False):
        assert before == after or before is None or after is None


def test_frame_margin_matches_the_m4td_default():
    """Cinco quadros de cada lado de cada corte — a `DEFAULT_MARGIN` do M4TD.

    A janela de tempo é zerada para isolar a de quadros: com passo enorme entre
    amostras, o embargo em segundos não alcançaria vizinho nenhum, e o que
    sobra de descarte é só a margem em quadros.
    """
    stamps = _frames(600, step_ms=1_000_000)
    result = assign_temporal_splits(stamps, SplitConfig(embargo_seconds=0, embargo_frames=5))

    assert result.embargoed == 2 * 2 * 5  # dois cortes, cinco quadros de cada lado
    assert result.embargo_frames_applied == 5


def test_the_frame_margin_shrinks_instead_of_emptying_a_partition():
    stamps = _frames(12, step_ms=1000)
    result = assign_temporal_splits(stamps, SplitConfig(embargo_seconds=0, embargo_frames=5))

    assert result.embargo_frames_applied < 5
    assert result.valid > 0 and result.test > 0
    assert any(warning.code == "margem_reduzida" for warning in result.warnings)


def test_a_tiny_collection_goes_entirely_to_train_and_says_so():
    """Menos que o mínimo não vira, calado, um dataset incapaz de medir."""
    result = assign_temporal_splits(_frames(6, step_ms=1000))

    assert (result.train, result.valid, result.test) == (6, 0, 0)
    warning = next(w for w in result.warnings if w.code == "dataset_curto")
    assert warning.level == "error"
