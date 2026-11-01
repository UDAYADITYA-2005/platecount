"""Turn SAM instances from several prompts and tiles into one list of colonies.

Box coordinates are inclusive pixels: a box from x1=0 to x2=9 is 10 pixels wide.
Tiles are PIL crop boxes, (left, top, right, bottom) with right and bottom exclusive.
"""
import math
from collections.abc import Mapping, Sequence

from PIL import Image
from pydantic import BaseModel

from platecount.meta.client import MetaClient
from platecount.meta.sam import DEFAULT_PROMPTS, SamInstance, encode_jpeg, segment

MAX_AREA_FRACTION = 0.05
MERGE_IOU = 0.5
MAX_MERGE_AREA_RATIO = 2.5
GRID = 3
OVERLAP = 0.2

Tile = tuple[int, int, int, int]


class MergeResult(BaseModel):
    colonies: list[SamInstance]  # best confidence first; nested boxes included
    nested: int  # how many colonies sit inside a much larger colony's box, for review


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


def _much_larger(big: SamInstance, small: SamInstance) -> bool:
    return _area(big) > MAX_MERGE_AREA_RATIO * _area(small)


def same_colony(a: SamInstance, b: SamInstance) -> bool:
    """IoU can't exceed 0.4 above the area ratio limit, so a nested pair never matches here."""
    if iou(a, b) > MERGE_IOU:
        return True
    similar_size = not _much_larger(a, b) and not _much_larger(b, a)
    return similar_size and (_centre_inside(a, b) or _centre_inside(b, a))


def is_nested(small: SamInstance, big: SamInstance) -> bool:
    return _much_larger(big, small) and _centre_inside(small, big)


def _on_border(box: SamInstance) -> bool:
    return box.x1 <= 0 or box.y1 <= 0 or box.x2 >= box.w - 1 or box.y2 >= box.h - 1


def is_candidate(box: SamInstance) -> bool:
    """False for boxes too large to be a colony or touching the image border."""
    too_large = _area(box) > MAX_AREA_FRACTION * box.w * box.h
    return not (too_large or _on_border(box))


def merge_prompts(by_prompt: Mapping[str, Sequence[SamInstance]]) -> MergeResult:
    """Filter, then keep the highest-confidence box of each colony, best first.

    Filtering comes first: a plate-sized box would otherwise mark every colony as nested.
    """
    boxes = [box for found in by_prompt.values() for box in found if is_candidate(box)]
    kept: list[SamInstance] = []
    for box in sorted(boxes, key=lambda b: b.confidence, reverse=True):
        if not any(same_colony(box, other) for other in kept):
            kept.append(box)
    nested = sum(any(is_nested(box, other) for other in kept) for box in kept)
    return MergeResult(colonies=kept, nested=nested)


def _spans(length: int) -> list[tuple[int, int]]:
    size = math.ceil(length / (GRID - (GRID - 1) * OVERLAP))
    starts = [round(i * (length - size) / (GRID - 1)) for i in range(GRID)]
    return [(start, start + size) for start in starts]


def tile_grid(width: int, height: int) -> list[Tile]:
    """Return GRID x GRID overlapping tiles, row by row, covering the whole image."""
    return [
        (left, top, right, bottom)
        for top, bottom in _spans(height)
        for left, right in _spans(width)
    ]


def segment_tiles(
    client: MetaClient, img: Image.Image, prompts: Sequence[str] = DEFAULT_PROMPTS
) -> list[dict[str, list[SamInstance]]]:
    """Run each prompt on each tile. Returns one result per tile, in tile coordinates."""
    return [
        segment(client, encode_jpeg(img.crop(tile)), prompts)
        for tile in tile_grid(*img.size)
    ]


def to_image_coords(box: SamInstance, tile: Tile, width: int, height: int) -> SamInstance:
    """Map a tile box to the full image. box.w and box.h give the size SAM saw the tile at."""
    left, top, right, bottom = tile
    scale_x = (right - left) / box.w
    scale_y = (bottom - top) / box.h
    return box.model_copy(
        update={
            "x1": left + round(box.x1 * scale_x),
            "y1": top + round(box.y1 * scale_y),
            "x2": left + round((box.x2 + 1) * scale_x) - 1,
            "y2": top + round((box.y2 + 1) * scale_y) - 1,
            "w": width,
            "h": height,
        }
    )


def merge_tiles(
    tiles: Sequence[Tile],
    found: Sequence[Mapping[str, Sequence[SamInstance]]],
    width: int,
    height: int,
) -> MergeResult:
    """Merge tile results across prompts and tiles.

    A box touching a tile edge may be a cut-off colony, so it goes before mapping; the
    neighbouring tile sees it whole. merge_prompts then judges size against the full image.
    """
    boxes = [
        to_image_coords(box, tile, width, height)
        for tile, by_prompt in zip(tiles, found, strict=True)
        for instances in by_prompt.values()
        for box in instances
        if not _on_border(box)
    ]
    return merge_prompts({"tiles": boxes})
