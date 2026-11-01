import pytest

from platecount.cfu import compute_cfu, range_flags

BELOW = "below_countable_range"
ABOVE = "above_countable_range"


def test_27_colonies_at_1e_minus_2_one_ml() -> None:
    r = compute_cfu(27, 0.01, 1.0)
    assert r.cfu_per_ml == 2700.0
    assert r.flags == []


@pytest.mark.parametrize(
    "n,expected",
    [(14, [BELOW]), (15, []), (300, []), (301, [ABOVE])],
)
def test_range_boundaries(n: int, expected: list[str]) -> None:
    assert range_flags(n) == expected
    assert compute_cfu(n, 0.01, 1.0).flags == expected


def test_volume_point_one_ml() -> None:
    assert compute_cfu(3, 1e-3, 0.1).cfu_per_ml == 30000.0
    assert compute_cfu(27, 0.01, 0.1).cfu_per_ml == 27000.0


def test_small_dilution_exact() -> None:
    assert compute_cfu(42, 1e-5, 1.0).cfu_per_ml == 4_200_000.0
    assert compute_cfu(42, 1e-5, 0.1).cfu_per_ml == 42_000_000.0


def test_zero_colonies() -> None:
    r = compute_cfu(0, 0.01, 1.0)
    assert r.cfu_per_ml == 0.0
    assert r.flags == [BELOW]


def test_spreader_alone_and_combined() -> None:
    assert range_flags(100, spreader=True) == ["spreader"]
    assert range_flags(10, spreader=True) == [BELOW, "spreader"]
    assert range_flags(400, spreader=True) == [ABOVE, "spreader"]
    assert compute_cfu(100, 0.01, 1.0, spreader=True).flags == ["spreader"]


def test_flagged_plate_still_reports_value() -> None:
    low = compute_cfu(14, 0.01, 1.0)
    high = compute_cfu(301, 0.01, 1.0)
    assert low.flags and low.cfu_per_ml == 1400.0
    assert high.flags and high.cfu_per_ml == 30100.0
    assert compute_cfu(100, 0.01, 1.0, spreader=True).cfu_per_ml == 10000.0


@pytest.mark.parametrize(
    "colonies,dilution,volume",
    [
        (-1, 0.01, 1.0),
        (10, 0.0, 1.0),
        (10, -0.01, 1.0),
        (10, 100, 1.0),
        (10, 1.0001, 1.0),
        (10, 0.01, 0.0),
        (10, 0.01, -1.0),
    ],
)
def test_invalid_inputs_raise(colonies: int, dilution: float, volume: float) -> None:
    with pytest.raises(ValueError):
        compute_cfu(colonies, dilution, volume)


def test_dilution_one_is_allowed() -> None:
    assert compute_cfu(20, 1.0, 1.0).cfu_per_ml == 20.0
