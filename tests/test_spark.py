import json
from pathlib import Path

import httpx
import pytest

from platecount.meta.client import MetaClient
from platecount.meta.spark import (
    MODEL,
    SparkParseError,
    parse_turn,
    respond,
    tool_result,
    usage_cost,
)

FIXTURES = Path(__file__).parent / "fixtures"
TURN1 = (FIXTURES / "spark_turn1.txt").read_text(encoding="utf-8")
TURN2 = (FIXTURES / "spark_turn2.txt").read_text(encoding="utf-8")


def completed(response: dict) -> str:
    event = {"type": "response.completed", "response": response}
    return f"event: response.completed\ndata: {json.dumps(event)}\n\n"


def scripted_client(tmp_path: Path, *replies: str) -> tuple[MetaClient, list[dict]]:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, text=replies[len(bodies) - 1])

    client = MetaClient(api_key="k", cache_dir=tmp_path, transport=httpx.MockTransport(handler))
    return client, bodies


def test_tool_turn_keeps_items_in_order_and_finds_the_call():
    turn = parse_turn(TURN1)
    assert [item["type"] for item in turn.output] == ["reasoning", "message", "function_call"]
    assert turn.output[1]["id"].startswith("rs_")  # a message, despite the id
    assert turn.output[1]["phase"] == "commentary"
    assert turn.output[0]["encrypted_content"]
    [call] = turn.calls
    assert call.name == "count_plate"
    assert call.call_id == "call_01a19afc4ed476fd96e79fba6ccfc059"
    assert json.loads(call.arguments)["path_hint"]


def test_text_turn_has_no_calls():
    turn = parse_turn(TURN2)
    assert turn.calls == []
    assert "70 colonies" in turn.text


def test_cost_uses_token_usage_with_reasoning_inside_output():
    # 1420 fresh input, 113 cached, 157 output of which 80 are reasoning.
    expected = (1420 * 1.25 + 113 * 0.15 + 157 * 4.25) / 1e6
    assert usage_cost(TURN1) == pytest.approx(expected)
    assert usage_cost(TURN1) == pytest.approx(0.0024592)


def test_second_request_replays_output_then_tool_result(tmp_path):
    client, bodies = scripted_client(tmp_path, TURN1, TURN2)
    user = {"role": "user", "content": "count"}
    first = respond(client, "be careful", [user], [])
    items = [user, *first.output, tool_result(first.calls[0].call_id, '{"count": 70}')]
    respond(client, "be careful", items, [])

    assert bodies[0]["model"] == MODEL
    assert bodies[0]["store"] is False
    assert bodies[0]["parallel_tool_calls"] is False
    assert bodies[0]["include"] == ["reasoning.encrypted_content"]
    sent = bodies[1]["input"]
    assert [item.get("type") for item in sent] == [
        None, "reasoning", "message", "function_call", "function_call_output"
    ]
    assert sent[1:4] == first.output  # unchanged, phase and encrypted_content included
    assert sent[4]["call_id"] == sent[3]["call_id"]
    assert client.cost.calls == 2
    assert client.cost.usd == pytest.approx(usage_cost(TURN1) + usage_cost(TURN2))


def test_same_conversation_is_served_from_cache_for_free(tmp_path):
    client, bodies = scripted_client(tmp_path, TURN1)
    items = [{"role": "user", "content": "count"}]
    assert respond(client, "x", items, []) == respond(client, "x", items, [])
    assert len(bodies) == 1
    assert client.cost.cache_hits == 1


def test_missing_usage_raises_with_raw_response():
    with pytest.raises(SparkParseError, match="while parsing"):
        parse_turn(completed({"status": "completed", "output": []}))


def test_incomplete_status_raises():
    usage = {"input_tokens": 1, "output_tokens": 1, "input_tokens_details": {"cached_tokens": 0}}
    with pytest.raises(SparkParseError, match="incomplete"):
        parse_turn(completed({"status": "incomplete", "output": [], "usage": usage}))


def test_no_completed_event_raises():
    with pytest.raises(SparkParseError, match="no response.completed"):
        usage_cost("event: response.created\n")
