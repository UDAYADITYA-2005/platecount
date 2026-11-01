"""Turn SAM instances from several prompts into one list of colonies.

Box coordinates are inclusive pixels: a box from x1=0 to x2=9 is 10 pixels wide.
"""
from collections.abc import Mapping, Sequence

from platecount.meta.sam import SamInstance

MAX_AREA_FRACTION = 0.05
MERGE_IOU = 0.5


def _area(box: SamInstance) -> int:
    return (box.x2 - box.x1 + 1) * (box.y2 - box.y1 + 1)


def iou(a: SamInstance, b: SamInstance) -> float:
    width = min(a.x2, b.x2) - max(a.x1, b.x1) + 1
    height = min(a.y2, b.y2) - max(a.y1, b.y1) + 1
    if width <= 0 or height <= 0:
        return 0.0
    overlap = width * height
    return overlap / (_area(a) + _area(b) - overlap)


def _centre_inside(inner: SamInstance, outer: SamInstance) -> bool:
    return (
        outer.x1 <= (inner.x1 + inner.x2) / 2 <= outer.x2
        and outer.y1 <= (inner.y1 + inner.y2) / 2 <= outer.y2
    )


def same_colony(a: SamInstance, b: SamInstance) -> bool:
    return iou(a, b) > MERGE_IOU or _centre_inside(a, b) or _centre_inside(b, a)


def is_candidate(box: SamInstance) -> bool:
    """False for boxes too large to be a colony or touching the image border."""
    too_large = _area(box) > MAX_AREA_FRACTION * box.w * box.h
    on_border = box.x1 <= 0 or box.y1 <= 0 or box.x2 >= box.w - 1 or box.y2 >= box.h - 1
    return not (too_large or on_border)


def merge_prompts(by_prompt: Mapping[str, Sequence[SamInstance]]) -> list[SamInstance]:
    """Filter, then keep the highest-confidence box of each colony, best first.

    Filtering comes first: a plate-sized box holds every colony's centre, so merging it
    would delete real colonies.
    """
    boxes = [box for found in by_prompt.values() for box in found if is_candidate(box)]
    kept: list[SamInstance] = []
    for box in sorted(boxes, key=lambda b: b.confidence, reverse=True):
        if not any(same_colony(box, other) for other in kept):
            kept.append(box)
    return kept
