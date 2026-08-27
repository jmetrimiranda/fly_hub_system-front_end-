"""O split temporal é a regra mais fácil de errar em silêncio — por isso testes."""

from datetime import UTC, datetime, timedelta

from app.models.enums import SplitName
from app.services.splitting import SplitConfig, assign_temporal_splits

START = datetime(2026, 8, 26, 14, 0, tzinfo=UTC)


def _frames(count: int, step_ms: int = 33) -> list[datetime]:
    return [START + timedelta(milliseconds=step_ms * i) for i in range(count)]


def test_empty_input_returns_empty_result():
    result = assign_temporal_splits([])
    assert result.assignments == []
    assert (result.train, result.valid, result.test) == (0, 0, 0)


def test_train_comes_before_valid_which_comes_before_test():
    stamps = _frames(1000, step_ms=1000)
    result = assign_temporal_splits(stamps, SplitConfig(embargo_seconds=0))

    by_split: dict[SplitName, list[datetime]] = {}
    for assignment in result.assignments:
        if assignment.split:
            by_split.setdefault(assignment.split, []).append(stamps[assignment.index])

    assert max(by_split[SplitName.TRAIN]) < min(by_split[SplitName.VALID])
    assert max(by_split[SplitName.VALID]) < min(by_split[SplitName.TEST])


def test_embargo_removes_frames_around_the_boundaries():
    stamps = _frames(600, step_ms=1000)
    without = assign_temporal_splits(stamps, SplitConfig(embargo_seconds=0))
    with_embargo = assign_temporal_splits(stamps, SplitConfig(embargo_seconds=10))

    assert without.embargoed == 0
    assert with_embargo.embargoed > 0
    assert with_embargo.train + with_embargo.valid + with_embargo.test < len(stamps)


def test_ratios_are_respected_within_rounding():
    stamps = _frames(1000, step_ms=1000)
    result = assign_temporal_splits(stamps, SplitConfig(0.8, 0.1, 0.1, embargo_seconds=0))
    assert result.train == 800
    assert abs(result.valid - 100) <= 1
    assert abs(result.test - 100) <= 1


def test_input_order_is_preserved_in_the_output():
    stamps = list(reversed(_frames(50, step_ms=1000)))
    result = assign_temporal_splits(stamps, SplitConfig(embargo_seconds=0))
    assert [a.index for a in result.assignments] == list(range(50))
    # O primeiro item da lista é o mais recente, logo deve cair em test.
    assert result.assignments[0].split == SplitName.TEST


def test_ratios_must_sum_to_one():
    import pytest

    with pytest.raises(ValueError, match="1.0"):
        SplitConfig(0.5, 0.5, 0.5)
