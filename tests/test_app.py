"""The API against a scripted Spark and recorded SAM responses. No network."""
import base64
import io
import json
import logging
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from platecount.agent.events import EVENTS_DIR
from platecount.api.app import (
    MAX_UPLOAD_BYTES,
    PLATES_PER_HOUR,
    RESERVE_USD,
    BadDilution,
    RateLimit,
    SpendCap,
    create_app,
    parse_dilution,
    parse_volume,
)
from platecount.meta.client import MetaAPIError, MetaClient
from test_loop import CFU, SAM_DOT, WHOLE, honest_finish, spark_reply

WEB = Path(__file__).parent.parent / "web"
HONEST = [WHOLE, ("view_overlay", {}), CFU, honest_finish]


def jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (300, 400), "gray").save(buffer, "JPEG")
    return buffer.getvalue()


class Harness:
    """An app whose clients all talk to one fake Meta API."""

    def __init__(self, tmp_path: Path, script: list, sam_down: bool = False, web: Path = WEB):
        self.script = list(script)
        self.sam_down = sam_down
        self.spark_calls = 0
        self.seen_cache_dirs: list[Path] = []
        self.spend_path = tmp_path / "spend.json"
        self.web = web
        self.app = self.build()
        self.http = TestClient(self.app)

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["model"] == "sam-3.1":
            return httpx.Response(500, text="sam down") if self.sam_down else httpx.Response(200, text=SAM_DOT)
        index = self.spark_calls
        self.spark_calls += 1
        if index >= len(self.script):
            return httpx.Response(401, text="script ran out")
        return httpx.Response(200, text=spark_reply(self.script[index], body, index))

    def client(self) -> MetaClient:
        return MetaClient(api_key="k", transport=httpx.MockTransport(self.handle), backoff_s=0)

    def build(self):
        return create_app(self.client, self.spend_path, self.web)

    def post(self, **params) -> httpx.Response:
        return self.http.post("/plates", content=jpeg(), params=params)


def test_plate_returns_report_overlay_flags_and_steps(tmp_path):
    h = Harness(tmp_path, HONEST)
    response = h.post(dilution="10^-2", volume_ml="1")
    assert response.status_code == 200
    body = response.json()
    report = body["report"]
    assert report["status"] == "verified"
    assert report["cfu_per_ml"] == report["colonies"] * 100
    assert Image.open(io.BytesIO(base64.b64decode(body["overlay_jpeg"]))).size
    assert [s["tool"] for s in body["steps"]] == [
        "segment_whole", "view_overlay", "compute_cfu", "finish", "verify",
    ]
    assert f"{report['colonies']} colonies found" in body["steps"][0]["summary"]
    assert str(report["cfu_per_ml"]) in body["steps"][2]["summary"]
    assert all(flag["text"] for flag in body["flags"])
    assert body["assumed"] == []


def test_left_out_inputs_are_assumed_and_named(tmp_path):
    body = Harness(tmp_path, [WHOLE, ("compute_cfu", {"dilution_exponent": 0, "volume_ml": 1}),
                              honest_finish]).post().json()
    assert body["assumed"] == ["dilution", "volume_ml"]
    assert body["report"]["cfu_per_ml"] == body["report"]["colonies"]


def test_rejected_run_stays_rejected(tmp_path):
    invented = ("finish", {"colonies": 999, "cfu_per_ml": 1.0})
    body = Harness(tmp_path, [WHOLE, CFU, invented]).post(dilution="1:100").json()
    assert body["report"]["status"] == "rejected"
    assert body["steps"][-1]["tool"] == "verify"
    assert "999" in body["steps"][-1]["summary"]


def test_refused_call_never_shows_its_text(tmp_path):
    bad = ("flag", '{"reason":"I counted 999 colonies"}')
    body = Harness(tmp_path, [bad, WHOLE, CFU, honest_finish]).post(dilution="0.01").json()
    assert body["steps"][0]["summary"] == "refused"
    assert "999" not in json.dumps(body["steps"][0])


@pytest.mark.parametrize(
    "text, exponent",
    [("10^-2", -2), (" 10^-2 ", -2), ("1:100", -2), ("0.01", -2), ("1e-3", -3), ("1:1", 0), ("1", 0),
     ("10^0", 0), ("1/1000", -3)],
)
def test_parse_dilution(text, exponent):
    assert parse_dilution(text) == exponent


@pytest.mark.parametrize(
    "text",
    ["1:50", "0.02", "10^2", "2^-2", "10^-2.5", "10^-400", "100", "0", "-0.01", "1:0", "nan", "inf", "abc", ""],
)
def test_parse_dilution_refuses(text):
    with pytest.raises(BadDilution):
        parse_dilution(text)


@pytest.mark.parametrize("text", ["0", "-1", "nan", "inf", "abc"])
def test_parse_volume_refuses(text):
    with pytest.raises(BadDilution):
        parse_volume(text)


def test_bad_inputs_cost_nothing(tmp_path):
    h = Harness(tmp_path, HONEST)
    assert h.post(dilution="1:50").status_code == 422
    assert h.post(volume_ml="0").status_code == 422
    assert h.http.post("/plates", content=b"not a photo").status_code == 415
    assert h.http.post("/plates", content=b"").status_code == 415
    assert h.spark_calls == 0
    assert h.app.state.limiter.hits == {}


def test_oversized_photo_is_refused(tmp_path):
    h = Harness(tmp_path, HONEST)
    assert h.http.post("/plates", content=b"x" * (MAX_UPLOAD_BYTES + 1)).status_code == 413


def test_oversized_photo_without_content_length_is_refused(tmp_path):
    def chunks():
        for _ in range(11):
            yield b"x" * (1024 * 1024)

    h = Harness(tmp_path, HONEST)
    assert h.http.post("/plates", content=chunks()).status_code == 413


def test_rate_limit_is_per_visitor():
    limit = RateLimit()
    assert all(limit.allow("a") for _ in range(PLATES_PER_HOUR))
    assert not limit.allow("a")
    assert limit.allow("b")


def test_old_hits_stop_counting(monkeypatch):
    limit = RateLimit()
    monkeypatch.setattr("platecount.api.app.time.time", lambda: 0.0)
    assert all(limit.allow("a") for _ in range(PLATES_PER_HOUR))
    monkeypatch.setattr("platecount.api.app.time.time", lambda: 3601.0)
    assert limit.allow("a")


def test_eleventh_plate_is_refused(tmp_path):
    h = Harness(tmp_path, HONEST)
    assert all(h.app.state.limiter.allow("testclient") for _ in range(PLATES_PER_HOUR))
    assert h.post().status_code == 429
    assert h.spark_calls == 0


def test_spend_cap_goes_demo_only_and_samples_keep_working(tmp_path):
    h = Harness(tmp_path, HONEST)
    h.app.state.cap.reserved_usd = h.app.state.cap.limit_usd
    response = h.post()
    assert response.status_code == 503
    assert response.json()["demo_only"] is True
    assert h.spark_calls == 0
    assert h.http.get("/samples").status_code == 200


def test_cap_survives_a_new_app(tmp_path):
    path = tmp_path / "spend.json"
    first = SpendCap(path, 1.0)
    assert first.reserve()
    first.settle(0.9)
    assert first.reserved_usd == 0
    assert not SpendCap(path, 1.0).reserve()


def test_cap_holds_parallel_runs_under_the_limit(tmp_path):
    cap = SpendCap(tmp_path / "spend.json", RESERVE_USD * 2)
    assert cap.reserve() and cap.reserve()
    assert not cap.reserve()


def test_yesterdays_spend_does_not_count(tmp_path):
    path = tmp_path / "spend.json"
    path.write_text(json.dumps({"date": "2020-01-01", "usd": 99}), encoding="utf-8")
    assert SpendCap(path, 1.0).reserve()


def test_unreadable_spend_file_stops_spending(tmp_path):
    path = tmp_path / "spend.json"
    path.write_text("{", encoding="utf-8")
    assert not SpendCap(path, 1.0).reserve()


def test_failed_run_returns_502_books_its_cost_and_releases_the_hold(tmp_path):
    h = Harness(tmp_path, [WHOLE], sam_down=True)
    response = h.post()
    assert response.status_code == 502
    assert "sam down" not in response.text
    assert h.app.state.cap.reserved_usd == 0
    assert json.loads(h.spend_path.read_text(encoding="utf-8"))["usd"] > 0


def test_paid_run_is_booked(tmp_path):
    h = Harness(tmp_path, HONEST)
    cost = h.post(dilution="1:100").json()["report"]["cost_usd"]
    assert json.loads(h.spend_path.read_text(encoding="utf-8"))["usd"] == pytest.approx(cost)


def test_no_api_key_means_demo_only(tmp_path):
    def no_key() -> MetaClient:
        raise MetaAPIError("MODEL_API_KEY is not set")

    response = TestClient(create_app(no_key, tmp_path / "s.json", WEB)).post("/plates", content=jpeg())
    assert response.status_code == 503
    assert response.json()["demo_only"] is True


def snapshot(*folders: Path) -> set[Path]:
    return {p for folder in folders for p in folder.rglob("*")}


def test_nothing_about_a_photo_stays_on_disk_or_in_logs(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)  # the default cache and events folders are relative
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp_root))
    h = Harness(tmp_path, HONEST)
    with caplog.at_level(logging.DEBUG):
        assert h.post(dilution="1:100").status_code == 200
    assert not Path(".cache").exists()
    assert not EVENTS_DIR.exists()
    assert list(temp_root.iterdir()) == []
    assert "�" not in caplog.text and "JFIF" not in caplog.text


def sample_web(tmp_path: Path) -> Path:
    web = tmp_path / "web"
    (web / "samples").mkdir(parents=True)
    (web / "index.html").write_text("page", encoding="utf-8")
    (web / "samples" / "index.json").write_text(
        json.dumps([{"id": "518", "label": "Dense"}]), encoding="utf-8"
    )
    (web / "samples" / "518.json").write_text('{"report": {"colonies": 256}}', encoding="utf-8")
    (web / "samples" / "secret.json").write_text("{}", encoding="utf-8")
    return web


def test_samples_list_and_result(tmp_path):
    h = Harness(tmp_path, [], web=sample_web(tmp_path))
    assert h.http.get("/samples").json() == [{"id": "518", "label": "Dense"}]
    assert h.http.get("/samples/518").json()["report"]["colonies"] == 256
    assert h.spark_calls == 0


def test_samples_refuse_ids_outside_the_index(tmp_path):
    h = Harness(tmp_path, [], web=sample_web(tmp_path))
    assert h.http.get("/samples/secret").status_code == 404
    assert h.http.get("/samples/..%2f..%2fspend").status_code == 404


def test_sample_overlay_is_a_404_when_it_was_not_deployed(tmp_path):
    h = Harness(tmp_path, [], web=sample_web(tmp_path))
    assert h.http.get("/samples/518/overlay.jpg").status_code == 404
    Image.new("RGB", (10, 10)).save(h.web / "samples" / "518.jpg")
    response = h.http.get("/samples/518/overlay.jpg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_static_page_is_served(tmp_path):
    h = Harness(tmp_path, [], web=sample_web(tmp_path))
    assert h.http.get("/").text == "page"


def test_page_follows_the_web_rules():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "Your photo is sent to Meta's API to count colonies and is deleted within 24 hours." in html
    assert 'accept="image/*" capture="environment"' in html
    assert 'name="viewport"' in html
    assert "CC BY-NC 2.0" in html
    assert "CFU/mL estimate" in html


def test_page_makes_no_banned_claims():
    text = " ".join(
        (WEB / name).read_text(encoding="utf-8").lower() for name in ("index.html", "app.js")
    )
    from platecount.api.app import FLAG_TEXT

    text += " ".join(FLAG_TEXT.values()).lower()
    for word in ("safe", "contaminat", "diagnos", "health"):
        assert word not in text


def test_every_flag_a_report_can_carry_has_plain_text():
    from platecount.agent.tools import FlagReason
    from platecount.api.app import FLAG_TEXT
    from platecount.cfu import Flag
    from typing import get_args

    assert set(get_args(FlagReason)) | set(get_args(Flag)) | {"agent_fallback"} == set(FLAG_TEXT)
