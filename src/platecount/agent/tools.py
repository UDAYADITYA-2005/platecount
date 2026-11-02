"""The tools Spark can call. Code owns the colony set; tools change it and return compact JSON.

Boxes in the set are always in full-image coordinates: whole-image boxes arrive in upload
pixels and tile boxes in image pixels, so they must not be mixed unconverted.
"""
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, ValidationError

from platecount.agent.events import EventLog, ToolEvent, input_hash
from platecount.cfu import CfuResult, compute_cfu
from platecount.counting import (
    GRID,
    PlateCount,
    count_tiled,
    count_whole,
    median_side,
    merge_prompts,
    merge_tiles,
    small_boxes,
    tile_grid,
    to_image_coords,
)
from platecount.meta.client import MetaClient
from platecount.meta.sam import SamInstance, encode_jpeg, segment

# Not dot + speck: on the same crop those would return the very response tiling already got.
RECHECK_PROMPTS = ("white dot", "round spot")
OVERLAY_SIDE = 1280

Cell = Literal[
    "r0c0", "r0c1", "r0c2", "r1c0", "r1c1", "r1c2", "r2c0", "r2c1", "r2c2"
]
FlagReason = Literal["small_specks", "prompt_disagreement", "too_many_to_count", "spreader"]


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RecheckArgs(NoArgs):
    cell: Cell


class CfuArgs(NoArgs):
    dilution_exponent: int
    volume_ml: float


class FlagArgs(NoArgs):
    reason: FlagReason


class FinishArgs(NoArgs):
    colonies: int
    cfu_per_ml: float


@dataclass
class PlateState:
    client: MetaClient
    img: Image.Image
    dilution_exponent: int
    volume_ml: float
    log: EventLog
    colonies: list[SamInstance] = field(default_factory=list)
    nested: int = 0
    flags: list[str] = field(default_factory=list)
    cfu: CfuResult | None = None
    claim: FinishArgs | None = None

    @cached_property
    def image_hash(self) -> str:
        return hashlib.sha256(self.img.tobytes()).hexdigest()


@dataclass
class ToolResult:
    output: dict
    image: bytes | None = None
    ok: bool = True


def _summary(state: PlateState, previous: int, hits: dict[str, int]) -> dict:
    return {
        "count": len(state.colonies),
        "previous": previous,
        "nested": state.nested,
        "small_specks": len(small_boxes(state.colonies)),
        "median_side": round(median_side(state.colonies)),
        "hits": hits,
    }


def _adopt(state: PlateState, counted: PlateCount) -> ToolResult:
    """Replace the colony set, as count_plate replaces a whole count with a tiled one."""
    previous = len(state.colonies)
    width, height = state.img.size
    full_image = (0, 0, width, height)
    state.colonies = [
        to_image_coords(box, full_image, width, height) for box in counted.merged.colonies
    ]
    state.nested = counted.merged.nested
    return ToolResult(_summary(state, previous, counted.prompt_hits))


def _segment_whole(state: PlateState, _: NoArgs) -> ToolResult:
    return _adopt(state, count_whole(state.client, state.img))


def _segment_tiled(state: PlateState, _: NoArgs) -> ToolResult:
    return _adopt(state, count_tiled(state.client, state.img))


def _recheck_cell(state: PlateState, args: RecheckArgs) -> ToolResult:
    """Add what other prompts find in one tile; boxes already in the set are not doubled."""
    previous = len(state.colonies)
    width, height = state.img.size
    row, column = int(args.cell[1]), int(args.cell[3])
    tile = tile_grid(width, height)[row * GRID + column]
    found = segment(state.client, encode_jpeg(state.img.crop(tile)), RECHECK_PROMPTS)
    new = merge_tiles([tile], [found], width, height)
    merged = merge_prompts({"kept": state.colonies, "recheck": new.colonies})
    state.colonies = merged.colonies
    state.nested = merged.nested
    return ToolResult(
        _summary(state, previous, {prompt: len(boxes) for prompt, boxes in found.items()})
    )


def overlay_jpeg(img: Image.Image, colonies: list[SamInstance]) -> bytes:
    """The plate with box outlines and the recheck cells marked, for Spark to look at."""
    shown = img.copy()
    draw = ImageDraw.Draw(shown)
    width, height = shown.size
    line = max(2, max(width, height) // 500)
    for box in colonies:
        draw.rectangle((box.x1, box.y1, box.x2, box.y2), outline="lime", width=line)
    for i in range(1, GRID):
        draw.line((width * i // GRID, 0, width * i // GRID, height), fill="yellow", width=line)
        draw.line((0, height * i // GRID, width, height * i // GRID), fill="yellow", width=line)
    for row in range(GRID):
        for column in range(GRID):
            corner = (width * column // GRID + 2 * line, height * row // GRID + 2 * line)
            draw.text(corner, f"r{row}c{column}", fill="yellow", font_size=height // 30)
    return encode_jpeg(shown, OVERLAY_SIDE)


def _view_overlay(state: PlateState, _: NoArgs) -> ToolResult:
    return ToolResult(
        {"count": len(state.colonies)}, image=overlay_jpeg(state.img, state.colonies)
    )


def _compute_cfu(state: PlateState, args: CfuArgs) -> ToolResult:
    wanted = (state.dilution_exponent, state.volume_ml)
    if (args.dilution_exponent, args.volume_ml) != wanted:
        return ToolResult({"error": f"this plate was given as {wanted}"}, ok=False)
    state.cfu = compute_cfu(
        len(state.colonies),
        float(10**args.dilution_exponent),
        args.volume_ml,
        spreader="spreader" in state.flags,
    )
    return ToolResult(state.cfu.model_dump())


def _flag(state: PlateState, args: FlagArgs) -> ToolResult:
    """Record a reason for review. A flag never changes the set: the count stays as it is."""
    output: dict = {"flag": args.reason, "recorded": True}
    if args.reason == "small_specks":
        output["boxes"] = len(small_boxes(state.colonies))
        output["recorded"] = output["boxes"] > 0
    if output["recorded"] and args.reason not in state.flags:
        state.flags.append(args.reason)
    return ToolResult(output)


def _finish(state: PlateState, args: FinishArgs) -> ToolResult:
    """Store Spark's claimed numbers for the verifier. Nothing here trusts them."""
    state.claim = args
    return ToolResult({"received": True})


@dataclass(frozen=True)
class Tool:
    args: type[NoArgs]
    description: str
    run: Callable[[PlateState, NoArgs], ToolResult]


TOOLS: dict[str, Tool] = {
    "segment_whole": Tool(
        NoArgs, "Segment the whole image. Replaces the colony set.", _segment_whole
    ),
    "segment_tiled": Tool(
        NoArgs, "Segment 9 overlapping tiles. Replaces the colony set.", _segment_tiled
    ),
    "view_overlay": Tool(
        NoArgs, "See the plate with the current boxes outlined and the cells labelled.",
        _view_overlay,
    ),
    "recheck_cell": Tool(
        RecheckArgs, "Look for missed colonies in one cell. Adds to the colony set.", _recheck_cell
    ),
    "compute_cfu": Tool(
        CfuArgs, "Compute CFU/mL from the current colony set. dilution_exponent -2 means 10^-2.",
        _compute_cfu,
    ),
    "flag": Tool(FlagArgs, "Flag the plate for a person to review.", _flag),
    "finish": Tool(
        FinishArgs, "End the run, copying count and cfu_per_ml from the latest tool outputs.",
        _finish,
    ),
}


def tool_definitions() -> list[dict]:
    """Definitions for Spark, generated from the same models that validate its arguments."""
    definitions = []
    for name, tool in TOOLS.items():
        schema = tool.args.model_json_schema()
        schema["required"] = list(schema["properties"])  # strict: an empty model omits the key
        definitions.append(
            {
                "type": "function",
                "name": name,
                "description": tool.description,
                "parameters": schema,
                "strict": True,
            }
        )
    return definitions


def run_tool(state: PlateState, name: str, raw_args: str) -> ToolResult:
    """Run a tool and log it before anyone sees the result. Bad arguments return ok=False."""
    usd_before = state.client.cost.usd
    start = time.perf_counter()
    result = _dispatch(state, name, raw_args)
    state.log.append(
        ToolEvent(
            tool=name,
            args=raw_args,
            input_hash=input_hash(state.image_hash, name, raw_args),
            output=result.output,
            cost_usd=state.client.cost.usd - usd_before,
            ms=round((time.perf_counter() - start) * 1000),
        )
    )
    return result


def _dispatch(state: PlateState, name: str, raw_args: str) -> ToolResult:
    tool = TOOLS.get(name)
    if tool is None:
        return ToolResult({"error": f"unknown tool {name!r}"}, ok=False)
    try:
        args = tool.args.model_validate_json(raw_args or "{}")
    except ValidationError as exc:
        return ToolResult({"error": str(exc)}, ok=False)
    return tool.run(state, args)
