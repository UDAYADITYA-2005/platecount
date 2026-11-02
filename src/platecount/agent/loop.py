"""The agent: Spark picks the next tool, code does the work, the verifier judges the result.

A rejected report stays rejected. Only a failure to reach a report falls back to count_plate().
"""
import json
from base64 import b64encode
from typing import Literal

from PIL import Image
from pydantic import BaseModel

from platecount.agent.events import EventLog, ToolEvent, input_hash
from platecount.agent.tools import TOOLS, PlateState, adopt, run_tool, tool_definitions
from platecount.agent.verifier import verify
from platecount.cfu import compute_cfu, range_flags
from platecount.counting import TILE_FROM, count_plate
from platecount.meta.client import MetaAPIError, MetaClient
from platecount.meta.sam import SamInstance
from platecount.meta.spark import respond, tool_result

MAX_STEPS = 6
REASON_CHARS = 300  # API errors carry the whole raw response; the report keeps the start

INSTRUCTIONS = f"""You run the counting checks on one agar plate photo for a lab. You choose the \
next tool. You never count, estimate or do arithmetic yourself: every number comes from a tool, \
and a verifier rejects any number that doesn't match. Say nothing about health or safety.

What is known about the tools:
- segment_whole is precise, but misses colonies on crowded plates.
- segment_tiled finds more on crowded plates, but on sparse plates it adds many tiny false boxes.
- Guidance, fitted on only 16 plates, so use judgement: tile when segment_whole finds \
{TILE_FROM} or more.
- view_overlay shows you the plate: current boxes in green, cells r0c0..r2c2 in yellow. Use it \
when you doubt the count.
- recheck_cell looks for missed colonies in one cell. Use it when the overlay shows colonies \
without a green box. Boxes already in the set are not doubled.
- A tool's small_specks number counts boxes under 25% of the median side. They stay in the count; \
flag them for review.

Flags: small_specks when that number is above 0. prompt_disagreement when one prompt's hits are \
far from the other's. too_many_to_count when colonies are too crowded to separate. spreader when \
growth has spread into a film over the plate. A flag never changes the count.

You have {MAX_STEPS} tool calls in total, including compute_cfu and finish. After the last change \
to the colony set, call compute_cfu, then call finish with the count and cfu_per_ml copied exactly \
from compute_cfu's output."""


class Report(BaseModel):
    status: Literal["verified", "rejected", "fallback"]
    colonies: int  # the claimed number when rejected, so the reader sees what was refused
    cfu_per_ml: float
    flags: list[str]
    reason: str
    steps: list[str]
    cost_usd: float


class AgentResult(BaseModel):
    report: Report
    boxes: list[SamInstance]  # the code's colony set, whatever Spark claimed


class _Stop(RuntimeError):
    """The loop can't reach a report. The message says why."""


def _note(state: PlateState, name: str, output: dict) -> None:
    """Log a decision made by the loop itself, not by a tool Spark called."""
    state.log.append(
        ToolEvent(
            tool=name,
            args="",
            input_hash=input_hash(state.image_hash, name, ""),
            output=output,
            cost_usd=0,
            ms=0,
        )
    )


def _steps(state: PlateState) -> list[str]:
    return [event.tool for event in state.log.read() if event.tool in TOOLS]


def _flags(state: PlateState) -> list[str]:
    computed = range_flags(len(state.colonies), "spreader" in state.flags)
    return list(dict.fromkeys([*state.flags, *computed]))


def _final_report(state: PlateState) -> Report:
    claim = state.claim
    verdict = verify(state.log.read(), len(state.colonies), claim.colonies, claim.cfu_per_ml)
    _note(state, "verify", verdict.model_dump())
    return Report(
        status="verified" if verdict.ok else "rejected",
        colonies=claim.colonies,
        cfu_per_ml=claim.cfu_per_ml,
        flags=_flags(state),
        reason=verdict.reason,
        steps=_steps(state),
        cost_usd=0,
    )


def _image_message(jpeg: bytes) -> dict:
    data_url = "data:image/jpeg;base64," + b64encode(jpeg).decode("ascii")
    return {
        "role": "user",
        "content": [
            {"type": "input_text", "text": "The overlay you asked for."},
            {"type": "input_image", "image_url": data_url},
        ],
    }


def _text_message(text: str) -> dict:
    return {"role": "user", "content": [{"type": "input_text", "text": text}]}


def _drive(state: PlateState) -> Report:
    items = [
        _text_message(
            f"The plate photo is loaded. dilution_exponent={state.dilution_exponent}, "
            f"volume_ml={state.volume_ml}."
        )
    ]
    tools = tool_definitions()
    steps = 0
    refused = 0
    reminded = False
    while True:
        turn = respond(state.client, INSTRUCTIONS, items, tools)
        items += turn.output
        if not turn.calls:  # tool_choice can't force a call, and text is never a number source
            if reminded:
                raise _Stop("Spark ended without calling finish")
            reminded = True
            items.append(_text_message("Only tool calls count. End the run by calling finish."))
            continue
        images = []
        for call in turn.calls:
            if steps == MAX_STEPS:
                raise _Stop(f"no finish within {MAX_STEPS} tool steps")
            steps += 1
            result = run_tool(state, call.name, call.arguments)
            reply = {**result.output, "steps_left": MAX_STEPS - steps}
            items.append(tool_result(call.call_id, json.dumps(reply)))
            if not result.ok:
                refused += 1
                if refused > 1:
                    raise _Stop(f"second refused tool call: {result.output['error']}")
            if result.image:
                images.append(result.image)
            if state.claim:
                return _final_report(state)
        items += [_image_message(jpeg) for jpeg in images]


def _fallback(state: PlateState, cause: str) -> Report:
    """The fixed policy, with no Spark involved. A SAM outage here does raise: no count exists."""
    reason = f"agent failed, fixed policy used: {cause}"[:REASON_CHARS]
    adopt(state, count_plate(state.client, state.img))
    state.flags.insert(0, "agent_fallback")
    cfu = compute_cfu(
        len(state.colonies),
        float(10**state.dilution_exponent),
        state.volume_ml,
        spreader="spreader" in state.flags,
    )
    _note(state, "fallback", {"reason": reason, **cfu.model_dump()})
    return Report(
        status="fallback",
        colonies=cfu.colonies,
        cfu_per_ml=cfu.cfu_per_ml,
        flags=_flags(state),
        reason=reason,
        steps=_steps(state),
        cost_usd=0,
    )


def run_agent(
    client: MetaClient,
    img: Image.Image,
    dilution_exponent: int,
    volume_ml: float,
    log: EventLog,
) -> AgentResult:
    """Count one plate. ValueError covers every parse error: Spark, SAM and bad JSON."""
    usd_before = client.cost.usd
    state = PlateState(client, img, dilution_exponent, volume_ml, log)
    try:
        report = _drive(state)
    except (_Stop, MetaAPIError, ValueError) as exc:
        report = _fallback(state, str(exc))
    report.cost_usd = client.cost.usd - usd_before
    return AgentResult(report=report, boxes=state.colonies)
