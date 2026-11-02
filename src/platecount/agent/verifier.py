"""Reject any reported number that no tool produced. No network, no I/O."""
from collections.abc import Sequence

from pydantic import BaseModel

from platecount.agent.events import ToolEvent

SEGMENT_TOOLS = ("segment_whole", "segment_tiled")


class Verdict(BaseModel):
    ok: bool
    reason: str


def verify(
    events: Sequence[ToolEvent], colony_count: int, colonies: int, cfu_per_ml: float
) -> Verdict:
    """Check claimed numbers against the current colony set and the logged outputs.

    An old logged value is not enough: the count must be today's set, and the CFU must come
    from the latest compute_cfu, run on that same count. Equality is exact on purpose.
    An empty set proves nothing unless a segmentation produced it, and recheck_cell sees one tile.
    """
    if not any(e.tool in SEGMENT_TOOLS and "count" in e.output for e in events):
        return Verdict(ok=False, reason="no segment_whole or segment_tiled output exists")
    if colonies != colony_count:
        return Verdict(
            ok=False, reason=f"reported {colonies} colonies, the colony set holds {colony_count}"
        )
    outputs = [e.output for e in events if e.tool == "compute_cfu" and "cfu_per_ml" in e.output]
    if not outputs:
        return Verdict(ok=False, reason=f"reported {cfu_per_ml} CFU/mL, no compute_cfu output exists")
    latest = outputs[-1]
    if cfu_per_ml != latest["cfu_per_ml"]:
        return Verdict(
            ok=False,
            reason=f"reported {cfu_per_ml} CFU/mL, compute_cfu returned {latest['cfu_per_ml']}",
        )
    if latest["colonies"] != colony_count:
        return Verdict(
            ok=False,
            reason=(
                f"CFU/mL was computed on {latest['colonies']} colonies, "
                f"the colony set now holds {colony_count}"
            ),
        )
    return Verdict(ok=True, reason="every number matches a tool output")
