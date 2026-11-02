from platecount.agent.events import ToolEvent
from platecount.agent.verifier import verify


def event(tool: str, output: dict) -> ToolEvent:
    return ToolEvent(tool=tool, args="{}", input_hash="h", output=output, cost_usd=0, ms=1)


def cfu_event(colonies: int, cfu: float) -> ToolEvent:
    return event("compute_cfu", {"colonies": colonies, "cfu_per_ml": cfu})


SEGMENTED = event("segment_whole", {"count": 27})


def test_numbers_from_tools_pass():
    assert verify([SEGMENTED, cfu_event(27, 2700.0)], 27, 27, 2700.0).ok


def test_integer_cfu_equals_the_same_float():
    assert verify([SEGMENTED, cfu_event(27, 2700.0)], 27, 27, 2700).ok


def test_invented_count_is_rejected():
    verdict = verify([SEGMENTED, cfu_event(27, 2700.0)], 27, 999, 2700.0)
    assert not verdict.ok
    assert "999" in verdict.reason


def test_invented_cfu_is_rejected():
    verdict = verify([SEGMENTED, cfu_event(27, 2700.0)], 27, 27, 2800.0)
    assert not verdict.ok
    assert "2800.0" in verdict.reason


def test_rounded_cfu_is_rejected():
    assert not verify([SEGMENTED, cfu_event(7, 2333.3333)], 7, 7, 2333.33).ok


def test_cfu_with_no_compute_cfu_output_is_rejected():
    assert not verify([event("segment_whole", {"count": 27})], 27, 27, 2700.0).ok


def test_refused_compute_cfu_does_not_count():
    assert not verify([SEGMENTED, event("compute_cfu", {"error": "no"})], 27, 27, 2700.0).ok


def test_cfu_computed_before_the_set_changed_is_rejected():
    verdict = verify([SEGMENTED, cfu_event(27, 2700.0)], 30, 30, 2700.0)
    assert not verdict.ok
    assert "27" in verdict.reason


def test_old_count_from_the_log_is_rejected():
    events = [event("segment_whole", {"count": 63}), cfu_event(256, 25600.0)]
    assert not verify(events, 256, 63, 25600.0).ok


def test_only_the_latest_cfu_counts():
    events = [SEGMENTED, cfu_event(27, 2700.0), cfu_event(30, 3000.0)]
    assert verify(events, 30, 30, 3000.0).ok
    assert not verify(events, 30, 30, 2700.0).ok


def test_zero_from_a_plate_never_segmented_is_rejected():
    verdict = verify([cfu_event(0, 0.0)], 0, 0, 0.0)
    assert not verdict.ok
    assert "segment" in verdict.reason


def test_refused_segmentation_does_not_count():
    refused = event("segment_whole", {"error": "no"})
    assert not verify([refused, cfu_event(0, 0.0)], 0, 0, 0.0).ok


def test_a_recheck_alone_is_not_a_segmented_plate():
    recheck = event("recheck_cell", {"count": 3})
    assert not verify([recheck, cfu_event(3, 300.0)], 3, 3, 300.0).ok


def test_an_empty_plate_that_was_segmented_passes():
    empty = event("segment_tiled", {"count": 0})
    assert verify([empty, cfu_event(0, 0.0)], 0, 0, 0.0).ok
