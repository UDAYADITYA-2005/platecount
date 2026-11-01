"""CFU/mL math and FDA BAM Chapter 3 flags. No network, no I/O."""

from fractions import Fraction
from typing import Literal

from pydantic import BaseModel

COUNTABLE_MIN = 15
COUNTABLE_MAX = 300

Flag = Literal["below_countable_range", "above_countable_range", "spreader"]


class CfuResult(BaseModel):
    colonies: int
    dilution: float
    volume_ml: float
    cfu_per_ml: float
    flags: list[Flag]


def range_flags(colonies: int, spreader: bool = False) -> list[Flag]:
    """Flags for a person to review. A flagged plate is still reported."""
    flags: list[Flag] = []
    if colonies < COUNTABLE_MIN:
        flags.append("below_countable_range")
    elif colonies > COUNTABLE_MAX:
        flags.append("above_countable_range")
    if spreader:
        flags.append("spreader")
    return flags


def compute_cfu(
    colonies: int, dilution: float, volume_ml: float, spreader: bool = False
) -> CfuResult:
    """CFU/mL = colonies / (dilution x volume plated in mL).

    `dilution` is the fraction plated: 0.01 for 10^-2, not 100.
    """
    if colonies < 0:
        raise ValueError(f"colonies must be >= 0, got {colonies}")
    if not 0 < dilution <= 1:
        raise ValueError(f"dilution must be in (0, 1], got {dilution}")
    if volume_ml <= 0:
        raise ValueError(f"volume_ml must be > 0, got {volume_ml}")

    # Exact fractions, so 0.01 x 0.1 float noise never reaches the verifier's equality check.
    cfu = colonies / (Fraction(str(dilution)) * Fraction(str(volume_ml)))
    return CfuResult(
        colonies=colonies,
        dilution=dilution,
        volume_ml=volume_ml,
        cfu_per_ml=float(cfu),
        flags=range_flags(colonies, spreader),
    )
