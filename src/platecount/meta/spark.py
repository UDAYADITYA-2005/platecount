"""Muse Spark 1.3: one turn of a stateless tool loop.

Response shape comes from tests/fixtures/spark_turn1.txt and spark_turn2.txt. Items are told
apart by `type` only: the fixture's commentary message carries an rs_ id, like a reasoning item.
The caller keeps the conversation and replays `SparkTurn.output` unchanged on the next turn.
"""
import json

from pydantic import BaseModel, ValidationError

from platecount.meta.client import MetaClient, cache_key, completed_response

MODEL = "muse-spark-1.3"
USD_PER_M_INPUT = 1.25
USD_PER_M_CACHED = 0.15
USD_PER_M_OUTPUT = 4.25


class SparkParseError(ValueError):
    """A Spark response did not have the expected shape. The message holds the raw response."""


class ToolCall(BaseModel):
    call_id: str
    name: str
    arguments: str  # a JSON string; the tool layer validates it


class SparkTurn(BaseModel):
    output: list[dict]  # every output item as received, for replay
    calls: list[ToolCall]
    text: str


class _InputDetails(BaseModel):
    cached_tokens: int


class _Usage(BaseModel):
    input_tokens: int  # includes cached_tokens
    output_tokens: int  # includes reasoning tokens: input + output == total in both fixtures
    input_tokens_details: _InputDetails


class _Part(BaseModel):
    type: str
    text: str = ""


class _Message(BaseModel):
    content: list[_Part]


class _Response(BaseModel):
    status: str
    output: list[dict]
    usage: _Usage


def _parse(raw: str) -> _Response:
    completed = completed_response(raw)
    if completed is None:
        raise SparkParseError(f"no response.completed event:\n{raw}")
    try:
        return _Response.model_validate(completed)
    except ValidationError as exc:
        raise SparkParseError(f"{exc!r} while parsing:\n{raw}") from exc


def usage_cost(raw: str) -> float:
    """USD for one response, from its own token usage. Reasoning bills inside output_tokens."""
    usage = _parse(raw).usage
    cached = usage.input_tokens_details.cached_tokens
    return (
        (usage.input_tokens - cached) * USD_PER_M_INPUT
        + cached * USD_PER_M_CACHED
        + usage.output_tokens * USD_PER_M_OUTPUT
    ) / 1_000_000


def parse_turn(raw: str) -> SparkTurn:
    response = _parse(raw)
    if response.status != "completed":
        raise SparkParseError(f"response status {response.status!r}:\n{raw}")
    calls: list[ToolCall] = []
    text: list[str] = []
    try:
        for item in response.output:
            if item.get("type") == "function_call":
                calls.append(ToolCall.model_validate(item))
            elif item.get("type") == "message":
                parts = _Message.model_validate(item).content
                text += [part.text for part in parts if part.type == "output_text"]
    except ValidationError as exc:
        raise SparkParseError(f"{exc!r} while parsing:\n{raw}") from exc
    return SparkTurn(output=response.output, calls=calls, text="".join(text))


def tool_result(call_id: str, output: str) -> dict:
    return {"type": "function_call_output", "call_id": call_id, "output": output}


def respond(
    client: MetaClient, instructions: str, items: list[dict], tools: list[dict]
) -> SparkTurn:
    """Send the whole conversation and return Spark's next turn.

    client adds store:false and stream:true. The key covers the full body, so a rerun of
    the same conversation replays from disk for free.
    """
    body = {
        "model": MODEL,
        "instructions": instructions,
        "input": items,
        "tools": tools,
        "parallel_tool_calls": False,
        "include": ["reasoning.encrypted_content"],
    }
    key = cache_key(MODEL, json.dumps(body, sort_keys=True), b"", {})
    return parse_turn(client.post_stream(key, body, usage_cost))
