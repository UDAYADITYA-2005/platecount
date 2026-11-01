"""Count accuracy metrics. Pure functions over (found, true) pairs."""
from collections.abc import Sequence

from pydantic import BaseModel


class Metrics(BaseModel):
    plates: int
    mae: float
    smape: float  # percent, 0-200
    within_10pct: float  # percent of plates


def _smape_term(found: int, true: int) -> float:
    """0/0 is a perfect count, so it scores 0 rather than dividing by zero."""
    return 2 * abs(found - true) / (found + true) if found + true else 0.0


def summarize(pairs: Sequence[tuple[int, int]]) -> Metrics:
    """Raises ValueError on no pairs: an average over zero plates is not a number to report."""
    if not pairs:
        raise ValueError("no plates to summarize")
    n = len(pairs)
    return Metrics(
        plates=n,
        mae=sum(abs(found - true) for found, true in pairs) / n,
        smape=100 * sum(_smape_term(found, true) for found, true in pairs) / n,
        within_10pct=100 * sum(abs(found - true) <= 0.1 * true for found, true in pairs) / n,
    )
