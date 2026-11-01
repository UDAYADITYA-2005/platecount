import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from platecount.meta.client import MetaClient
from platecount.meta.sam import SamParseError, parse_stream, prepare_image, segment

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_real_colony_response():
    instances = parse_stream(fixture("sam_sweep_crop_dot.txt"))
    assert len(instances) == 31
    assert len({i.id for i in instances}) == 31
    for i in instances:
        assert (i.w, i.h) == (1024, 1024)
        assert 0 <= i.x1 <= i.x2 < i.w
        assert 0 <= i.y1 <= i.y2 < i.h
        assert 0 <= i.confidence <= 1
        assert "data=" in i.mask


def test_empty_response_gives_no_instances():
    assert parse_stream(fixture("sam_raw_1.txt")) == []


def test_mask_stays_attached_to_its_box():
    first = parse_stream(fixture("sam_sweep_crop_dot.txt"))[0]
    height, width = first.mask.split("data=")[1].split(",")[:2]
    assert (int(height), int(width)) == (first.y2 - first.y1 + 1, first.x2 - first.x1 + 1)


def test_broken_box_token_raises_with_raw_text():
    raw = fixture("sam_sweep_crop_dot.txt").replace(";y1=", ";yy=")
    with pytest.raises(SamParseError, match="response.completed"):
        parse_stream(raw)


def test_missing_confidence_raises():
    raw = fixture("sam_sweep_crop_dot.txt").replace(";c=", ";q=")
    with pytest.raises(SamParseError):
        parse_stream(raw)


def test_incomplete_stream_raises():
    with pytest.raises(SamParseError, match="no response.completed"):
        parse_stream("event: response.created\ndata: {}\n\n")


def test_segment_returns_instances_per_prompt_and_caches(tmp_path):
    replies = {"dot": "sam_sweep_crop_dot.txt", "speck": "sam_raw_1.txt"}
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body)
        return httpx.Response(200, text=fixture(replies[body["input"][0]["content"][0]["text"]]))

    client = MetaClient(
        api_key="test-key", cache_dir=tmp_path, transport=httpx.MockTransport(handler)
    )
    result = segment(client, b"jpeg", ["dot", "speck"])
    assert {prompt: len(found) for prompt, found in result.items()} == {"dot": 31, "speck": 0}
    assert all(body["store"] is False for body in sent)
    assert client.cost.usd == pytest.approx(0.005)

    segment(client, b"jpeg", ["dot", "speck"])
    assert len(sent) == 2
    assert client.cost.cache_hits == 2
    assert client.cost.usd == pytest.approx(0.005)


def test_prepare_image_downscales_and_keeps_aspect(tmp_path):
    path = tmp_path / "plate.jpg"
    Image.new("RGB", (3648, 2736), "white").save(path)
    out = Image.open(io.BytesIO(prepare_image(path)))
    assert out.format == "JPEG"
    assert out.size == (2048, 1536)
