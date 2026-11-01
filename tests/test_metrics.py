import pytest

from bench.metrics import summarize


def test_summarize():
    # errors 0, 10, 20 on true 100, 100, 20
    result = summarize([(100, 100), (110, 100), (40, 20)])
    assert result.plates == 3
    assert result.mae == pytest.approx(10)
    assert result.smape == pytest.approx(100 * (0 + 20 / 210 + 40 / 60) / 3)
    assert result.within_10pct == pytest.approx(200 / 3)


def test_zero_true_zero_found_is_perfect():
    result = summarize([(0, 0)])
    assert result.smape == 0
    assert result.within_10pct == 100


def test_found_on_empty_plate_is_not_within_10pct():
    result = summarize([(3, 0)])
    assert result.smape == 200
    assert result.within_10pct == 0


def test_no_plates_is_an_error():
    with pytest.raises(ValueError):
        summarize([])
