import json
from pathlib import Path

import httpx
import pytest

from platecount.meta.client import MetaAPIError, MetaClient, cache_key, completed_response

GOOD = "event: response.completed\ndata: {}\n\n"


def make_client(tmp_path: Path, handler) -> MetaClient:
    return MetaClient(
        api_key="test-key",
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),
        backoff_s=0,
    )


def counted(*responses: httpx.Response):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responses[min(len(calls), len(responses)) - 1]

    return handler, calls


def test_retries_429_then_succeeds(tmp_path):
    handler, calls = counted(httpx.Response(429, text="slow"), httpx.Response(200, text=GOOD))
    client = make_client(tmp_path, handler)
    assert client.post_stream("k", {}, 0.0025) == GOOD
    assert len(calls) == 2
    assert client.cost.calls == 1


def test_retries_connection_error(tmp_path):
    attempts = []

    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.ConnectError("down")
        return httpx.Response(200, text=GOOD)

    assert make_client(tmp_path, handler).post_stream("k", {}, 0.0025) == GOOD
    assert len(attempts) == 2


def test_gives_up_after_four_tries_on_500(tmp_path):
    handler, calls = counted(httpx.Response(500, text="boom"))
    client = make_client(tmp_path, handler)
    with pytest.raises(MetaAPIError, match="boom"):
        client.post_stream("k", {}, 0.0025)
    assert len(calls) == 4
    assert client.cost.usd == 0


def test_401_fails_fast_with_body(tmp_path):
    handler, calls = counted(httpx.Response(401, text="bad key"))
    with pytest.raises(MetaAPIError, match="HTTP 401: bad key"):
        make_client(tmp_path, handler).post_stream("k", {}, 0.0025)
    assert len(calls) == 1


def test_cache_hit_costs_nothing(tmp_path):
    handler, calls = counted(httpx.Response(200, text=GOOD))
    client = make_client(tmp_path, handler)
    client.post_stream("k", {}, 0.0025)
    assert client.post_stream("k", {}, 0.0025) == GOOD
    assert len(calls) == 1
    assert client.cost.usd == 0.0025
    assert client.cost.cache_hits == 1


def test_truncated_stream_is_not_cached_or_charged(tmp_path):
    handler, calls = counted(httpx.Response(200, text="event: response.created\n"))
    client = make_client(tmp_path, handler)
    with pytest.raises(MetaAPIError, match="without response.completed"):
        client.post_stream("k", {}, 0.0025)
    assert len(calls) == 4
    assert client.cost.usd == 0
    assert list(tmp_path.iterdir()) == []


def test_incomplete_response_is_charged_but_not_cached(tmp_path):
    event = json.dumps({"type": "response.completed", "response": {"status": "incomplete"}})
    bad = f"event: response.completed\ndata: {event}\n\n"
    handler, calls = counted(httpx.Response(200, text=bad))
    client = make_client(tmp_path, handler)
    for _ in range(2):  # a rerun goes back to the API instead of replaying the failure
        with pytest.raises(MetaAPIError, match="incomplete"):
            client.post_stream("k", {}, 0.0025)
    assert len(calls) == 2
    assert client.cost.usd == 0.005
    assert list(tmp_path.iterdir()) == []


def test_store_false_and_stream_are_always_sent(tmp_path):
    handler, calls = counted(httpx.Response(200, text=GOOD))
    make_client(tmp_path, handler).post_stream("k", {"store": True, "model": "m"}, 0)
    sent = json.loads(calls[0].content)
    assert sent["store"] is False
    assert sent["stream"] is True


def test_api_key_is_not_in_repr():
    assert "secret" not in repr(MetaClient(api_key="secret"))


def test_cache_key_changes_with_each_input():
    base = cache_key("m", "p", b"i", {"a": "1"})
    assert base != cache_key("n", "p", b"i", {"a": "1"})
    assert base != cache_key("m", "q", b"i", {"a": "1"})
    assert base != cache_key("m", "p", b"j", {"a": "1"})
    assert base != cache_key("m", "p", b"i", {"a": "2"})


def test_cost_can_come_from_the_response(tmp_path):
    handler, _ = counted(httpx.Response(200, text=GOOD))
    client = make_client(tmp_path, handler)
    client.post_stream("k", {}, lambda raw: len(raw) / 1000)
    assert client.cost.usd == len(GOOD) / 1000
    client.post_stream("k", {}, lambda raw: 99.0)
    assert client.cost.usd == len(GOOD) / 1000


def test_completed_response_finds_the_event():
    raw = 'data: {"type":"response.created"}\n\ndata: {"type":"response.completed","response":{"id":"r"}}\n'
    assert completed_response(raw) == {"id": "r"}
    assert completed_response("event: nothing\n") is None
