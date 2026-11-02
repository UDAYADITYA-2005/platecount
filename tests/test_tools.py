import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from platecount.agent.tools import PlateState, overlay_jpeg, run_tool, tool_definitions
from platecount.counting import small_boxes, tile_grid
from platecount.meta.client import MetaClient
from platecount.meta.sam import SamInstance, parse_stream

FIXTURES = Path(__file__).parent / "fixtures"
SAM_DOT = (FIXTURES / "sam_sweep_crop_dot.txt").read_text(encoding="utf-8")
SAM_EMPTY = (FIXTURES / "sam_sweep_crop_mold.txt").read_text(encoding="utf-8")


def box(x1: int, y1: int, side: int, size: int = 1000) -> SamInstance:
    return SamInstance(
        id=1, x1=x1, y1=y1, x2=x1 + side - 1, y2=y1 + side - 1, w=size, h=size,
        confidence=0.9, mask="",
    )


def make_state(tmp_path: Path, reply: str = SAM_DOT, dilution: int = -2, **kwargs) -> PlateState:
    client = MetaClient(
        api_key="k",
        cache_dir=tmp_path,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=reply)),
    )
    return PlateState(client, Image.new("RGB", (3000, 4000)), dilution, 1.0, **kwargs)


def test_every_definition_is_flat_strict_and_closed():
    for tool in tool_definitions():
        assert tool["type"] == "function" and tool["strict"] is True
        schema = tool["parameters"]
        assert schema["additionalProperties"] is False
        assert schema["required"] == list(schema["properties"])


def test_schema_enums_and_no_free_text():
    tools = {tool["name"]: tool["parameters"]["properties"] for tool in tool_definitions()}
    assert len(tools["recheck_cell"]["cell"]["enum"]) == 9
    assert len(tools["flag"]["reason"]["enum"]) == 4
    strings = [
        prop for props in tools.values() for prop in props.values()
        if prop["type"] == "string" and "enum" not in prop
    ]
    assert strings == []


def test_whole_boxes_are_stored_in_full_image_coordinates(tmp_path):
    state = make_state(tmp_path)
    result = run_tool(state, "segment_whole", "{}")
    expected = parse_stream(SAM_DOT)
    assert result.ok and result.output["count"] == len(state.colonies) > 0
    assert result.output["previous"] == 0
    assert result.output["hits"] == {"dot": len(expected), "speck": len(expected)}
    assert {(c.w, c.h) for c in state.colonies} == {(3000, 4000)}


def test_segment_tiled_replaces_the_set(tmp_path):
    state = make_state(tmp_path, colonies=[box(1, 1, 5)])
    result = run_tool(state, "segment_tiled", "")
    assert result.output["previous"] == 1
    assert box(1, 1, 5) not in state.colonies


def test_recheck_adds_to_the_set_without_doubling(tmp_path):
    state = make_state(tmp_path)
    kept = box(50, 60, 40, 3000).model_copy(update={"h": 4000})
    state.colonies = [kept]
    first = run_tool(state, "recheck_cell", '{"cell":"r1c2"}')
    assert first.ok and first.output["count"] > 1
    assert kept in state.colonies
    left, top, right, bottom = tile_grid(3000, 4000)[5]
    added = [c for c in state.colonies if c != kept]
    assert all(left <= c.x1 and c.x2 < right and top <= c.y1 and c.y2 < bottom for c in added)
    assert run_tool(state, "recheck_cell", '{"cell":"r1c2"}').output["count"] == first.output["count"]


def test_recheck_uses_other_prompts_than_segmentation(tmp_path):
    state = make_state(tmp_path, reply=SAM_EMPTY)
    assert set(run_tool(state, "recheck_cell", '{"cell":"r0c0"}').output["hits"]) == {
        "white dot", "round spot"
    }


def test_small_boxes_are_measured_against_the_median_side():
    colonies = [box(0, 0, 100), box(200, 0, 100), box(400, 0, 100), box(600, 0, 10)]
    assert small_boxes(colonies) == [colonies[3]]
    assert small_boxes([]) == []


def test_flag_records_a_reason_and_never_changes_the_set(tmp_path):
    colonies = [box(0, 0, 100), box(200, 0, 100), box(400, 0, 100), box(600, 0, 10)]
    state = make_state(tmp_path, colonies=list(colonies))
    assert run_tool(state, "flag", '{"reason":"small_specks"}').output["boxes"] == 1
    assert state.flags == ["small_specks"]
    assert state.colonies == colonies


def test_small_specks_flag_is_refused_when_there_are_none(tmp_path):
    state = make_state(tmp_path, colonies=[box(0, 0, 100)])
    assert run_tool(state, "flag", '{"reason":"small_specks"}').output["recorded"] is False
    assert state.flags == []


def test_compute_cfu_uses_the_set_size_and_spreader_flag(tmp_path):
    state = make_state(tmp_path, colonies=[box(i * 20, 0, 10) for i in range(27)])
    run_tool(state, "flag", '{"reason":"spreader"}')
    result = run_tool(state, "compute_cfu", '{"dilution_exponent":-2,"volume_ml":1}')
    assert result.output["cfu_per_ml"] == 2700.0
    assert "spreader" in result.output["flags"]


def test_compute_cfu_refuses_values_that_differ_from_the_run(tmp_path):
    state = make_state(tmp_path, colonies=[box(0, 0, 10)])
    result = run_tool(state, "compute_cfu", '{"dilution_exponent":-3,"volume_ml":1}')
    assert not result.ok
    assert state.cfu is None


@pytest.mark.parametrize(
    "name, raw",
    [
        ("recheck_cell", '{"cell":"r3c3"}'),
        ("recheck_cell", "{}"),
        ("flag", '{"reason":"looks odd"}'),
        ("segment_whole", '{"prompt":"colony"}'),
        ("compute_cfu", '{"dilution_exponent":"-2","volume_ml":1}'),
        ("finish", "not json"),
        ("delete_plate", "{}"),
    ],
)
def test_bad_arguments_are_refused_with_a_reason(tmp_path, name, raw):
    result = run_tool(make_state(tmp_path), name, raw)
    assert not result.ok
    assert result.output["error"]


def test_finish_only_stores_the_claim(tmp_path):
    state = make_state(tmp_path)
    assert run_tool(state, "finish", '{"colonies":999,"cfu_per_ml":99900}').ok
    assert state.claim.colonies == 999
    assert state.colonies == []


def test_overlay_returns_an_image_and_json_without_it(tmp_path):
    state = make_state(tmp_path, colonies=[box(10, 10, 100)])
    result = run_tool(state, "view_overlay", "{}")
    assert result.output == {"count": 1}
    json.dumps(result.output)
    assert max(Image.open(io.BytesIO(result.image)).size) == 1280


def test_overlay_outlines_boxes():
    img = Image.new("RGB", (1000, 1000))
    shown = Image.open(io.BytesIO(overlay_jpeg(img, [box(100, 100, 300)])))
    assert shown.getpixel((250, 100))[1] > 150  # top edge of the box
    assert shown.getpixel((250, 250)) == pytest.approx((0, 0, 0), abs=10)  # inside stays dark
