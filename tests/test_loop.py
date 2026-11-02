"""The loop against a scripted Spark and recorded SAM responses. No network."""
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from PIL import Image

from platecount.agent.events import EventLog
from platecount.agent.loop import AgentResult, run_agent
from platecount.counting import count_plate
from platecount.meta.client import MetaClient

FIXTURES = Path(__file__).parent / "fixtures"
SAM_DOT = (FIXTURES / "sam_sweep_crop_dot.txt").read_text(encoding="utf-8")
USAGE = {"input_tokens": 1000, "output_tokens": 100, "input_tokens_details": {"cached_tokens": 0}}

Step = tuple[str, dict | str] | str | Callable[[dict], tuple[str, dict]]


def sse(output: list[dict]) -> str:
    response = {"status": "completed", "output": output, "usage": USAGE}
    event = json.dumps({"type": "response.completed", "response": response})
    return f"event: response.completed\ndata: {event}\n\n"


def spark_reply(step: Step, body: dict, index: int) -> str:
    """A str step is a plain text reply. A callable reads the conversation, as Spark would."""
    if isinstance(step, str):
        return sse([{"type": "message", "role": "assistant", "id": f"m{index}",
                     "content": [{"type": "output_text", "text": step}]}])
    name, args = step(body) if callable(step) else step
    arguments = args if isinstance(args, str) else json.dumps(args)
    return sse([{"type": "function_call", "id": f"rs_{index}", "call_id": f"call_{index}",
                 "name": name, "arguments": arguments, "status": "completed"}])


def last_output(body: dict) -> dict:
    outputs = [i for i in body["input"] if i.get("type") == "function_call_output"]
    return json.loads(outputs[-1]["output"])


def honest_finish(body: dict) -> tuple[str, dict]:
    cfu = last_output(body)
    return "finish", {"colonies": cfu["colonies"], "cfu_per_ml": cfu["cfu_per_ml"]}


CFU = ("compute_cfu", {"dilution_exponent": -2, "volume_ml": 1})
WHOLE = ("segment_whole", {})


class Fake:
    """Serves Spark from a script and SAM from a fixture, recording what was sent."""

    def __init__(self, tmp_path: Path, script: list[Step], sam_failures: int = 0):
        self.script = script
        self.sam_failures = sam_failures
        self.spark_bodies: list[dict] = []
        self.client = MetaClient(
            api_key="k",
            cache_dir=tmp_path / "cache",
            transport=httpx.MockTransport(self.handle),
            backoff_s=0,
        )
        self.log = EventLog(tmp_path / "events.jsonl")

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["model"] == "sam-3.1":
            if self.sam_failures:
                self.sam_failures -= 1
                return httpx.Response(500, text="sam down")
            return httpx.Response(200, text=SAM_DOT)
        index = len(self.spark_bodies)
        self.spark_bodies.append(body)
        if index >= len(self.script):
            return httpx.Response(500, text="script ran out")
        return httpx.Response(200, text=spark_reply(self.script[index], body, index))

    def run(self) -> AgentResult:
        img = Image.new("RGB", (300, 400))
        return run_agent(self.client, img, -2, 1.0, self.log)


def test_honest_run_is_verified_and_logged(tmp_path):
    fake = Fake(tmp_path, [WHOLE, ("view_overlay", {}), CFU, honest_finish])
    result = fake.run()
    report = result.report
    assert report.status == "verified"
    assert report.colonies == len(result.boxes) > 0
    assert report.cfu_per_ml == report.colonies * 100
    assert report.steps == ["segment_whole", "view_overlay", "compute_cfu", "finish"]
    assert report.cost_usd > 0
    assert [e.tool for e in fake.log.read()][-1] == "verify"


def test_invented_count_ends_rejected_with_the_reason(tmp_path):
    invented = lambda body: ("finish", {"colonies": 999, "cfu_per_ml": last_output(body)["cfu_per_ml"]})
    result = Fake(tmp_path, [WHOLE, CFU, invented]).run()
    assert result.report.status == "rejected"
    assert result.report.colonies == 999
    assert "999" in result.report.reason
    assert len(result.boxes) != 999  # no silent fix, and the set stays the code's


def test_finish_without_compute_cfu_is_rejected(tmp_path):
    result = Fake(tmp_path, [WHOLE, ("finish", {"colonies": 1, "cfu_per_ml": 100})]).run()
    assert result.report.status == "rejected"


def test_cfu_computed_before_segmenting_is_rejected(tmp_path):
    fake = Fake(tmp_path, [CFU, WHOLE, ("view_overlay", {}), lambda body: (
        "finish", {"colonies": last_output(body)["count"], "cfu_per_ml": 0}
    )])
    assert fake.run().report.status == "rejected"


def test_zero_report_without_segmenting_is_rejected(tmp_path):
    report = Fake(tmp_path, [CFU, honest_finish]).run().report
    assert report.status == "rejected"
    assert "segment" in report.reason


def test_overlay_goes_in_a_user_message_after_its_tool_result(tmp_path):
    fake = Fake(tmp_path, [WHOLE, ("view_overlay", {}), CFU, honest_finish])
    fake.run()
    sent = fake.spark_bodies[2]["input"]
    assert sent[-2]["type"] == "function_call_output"
    assert sent[-1]["role"] == "user"
    assert sent[-1]["content"][1]["image_url"].startswith("data:image/jpeg;base64,")


def test_first_message_gives_the_inputs_and_tools(tmp_path):
    fake = Fake(tmp_path, [WHOLE, CFU, honest_finish])
    fake.run()
    first = fake.spark_bodies[0]
    assert "dilution_exponent=-2" in first["input"][0]["content"][0]["text"]
    assert "56" in first["instructions"]
    assert {tool["name"] for tool in first["tools"]} >= {"recheck_cell", "finish"}


def test_steps_left_counts_down(tmp_path):
    fake = Fake(tmp_path, [WHOLE, CFU, honest_finish])
    fake.run()
    assert last_output(fake.spark_bodies[1])["steps_left"] == 5


def test_step_limit_falls_back_to_the_policy_with_a_flag(tmp_path):
    fake = Fake(tmp_path, [WHOLE] * 7)
    result = fake.run()
    assert result.report.status == "fallback"
    assert "agent_fallback" in result.report.flags
    assert "6 tool steps" in result.report.reason
    assert result.report.steps == ["segment_whole"] * 6
    img = Image.new("RGB", (300, 400))
    assert result.report.colonies == len(count_plate(fake.client, img).merged.colonies)


def test_malformed_arguments_get_one_retry(tmp_path):
    script = [("recheck_cell", '{"cell":"r9c9"}'), WHOLE, CFU, honest_finish]
    fake = Fake(tmp_path, script)
    assert fake.run().report.status == "verified"
    assert "error" in last_output(fake.spark_bodies[1])


def test_second_malformed_call_falls_back(tmp_path):
    bad = ("flag", '{"reason":"nope"}')
    report = Fake(tmp_path, [bad, bad]).run().report
    assert report.status == "fallback"
    assert "second refused" in report.reason


def test_text_reply_gets_one_reminder_and_its_numbers_are_ignored(tmp_path):
    fake = Fake(tmp_path, [WHOLE, CFU, "I counted 999 colonies.", honest_finish])
    report = fake.run().report
    assert report.status == "verified"
    assert report.colonies != 999


def test_two_text_replies_fall_back(tmp_path):
    report = Fake(tmp_path, ["I counted 999.", "Still 999."]).run().report
    assert report.status == "fallback"
    assert report.colonies != 999


def test_sam_outage_during_a_tool_falls_back_when_sam_returns(tmp_path):
    report = Fake(tmp_path, [WHOLE], sam_failures=4).run().report
    assert report.status == "fallback"
    assert report.colonies > 0
    assert "sam down" in report.reason
    assert len(report.reason) <= 300


def test_fallback_is_logged(tmp_path):
    fake = Fake(tmp_path, ["a", "b"])
    fake.run()
    assert fake.log.read()[-1].tool == "fallback"


def test_rerun_of_the_same_plate_costs_nothing(tmp_path):
    script = [WHOLE, ("view_overlay", {}), CFU, honest_finish]
    first = Fake(tmp_path, script)
    assert first.run().report.status == "verified"
    second = Fake(tmp_path, script)
    assert second.run().report.cost_usd == 0
    assert second.client.cost.calls == 0


@pytest.mark.parametrize(
    "exponent, volume", [(2, 1.0), (-400, 1.0), (-2, 0.0), (-2, -1.0), (-2, float("nan"))]
)
def test_bad_dilution_or_volume_is_refused_before_any_paid_call(tmp_path, exponent, volume):
    fake = Fake(tmp_path, [WHOLE, CFU, honest_finish])
    img = Image.new("RGB", (300, 400))
    with pytest.raises(ValueError):
        run_agent(fake.client, img, exponent, volume, fake.log)
    assert fake.client.cost.calls == 0
    assert fake.log.read() == []
