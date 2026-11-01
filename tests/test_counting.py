from pathlib import Path

import pytest

from platecount.counting import iou, is_candidate, merge_prompts, same_colony
from platecount.meta.sam import SamInstance, parse_stream

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> list[SamInstance]:
    return parse_stream((FIXTURES / name).read_text(encoding="utf-8"))


def box(x1: int, y1: int, x2: int, y2: int, confidence: float = 0.5) -> SamInstance:
    return SamInstance(
        id=0, x1=x1, y1=y1, x2=x2, y2=y2, w=1000, h=1000, confidence=confidence, mask=""
    )


def test_iou_counts_inclusive_pixels():
    assert iou(box(10, 10, 19, 19), box(10, 10, 19, 19)) == 1.0
    assert iou(box(10, 10, 19, 19), box(20, 10, 29, 19)) == 0.0
    assert iou(box(10, 10, 19, 19), box(19, 19, 28, 28)) == pytest.approx(1 / 199)


def test_iou_of_boxes_sharing_two_thirds_is_half():
    assert iou(box(100, 100, 129, 109), box(110, 100, 139, 109)) == 0.5


def test_centre_inside_merges_at_low_iou():
    outer, inner = box(100, 100, 199, 199), box(140, 140, 149, 149)
    assert iou(outer, inner) < 0.5
    assert same_colony(outer, inner)
    assert same_colony(inner, outer)


def test_overlapping_boxes_with_centres_outside_stay_apart():
    assert not same_colony(box(100, 100, 119, 119), box(115, 115, 134, 134))


def test_higher_confidence_box_wins_in_any_order():
    weak, strong = box(100, 100, 119, 119, 0.6), box(101, 101, 120, 120, 0.9)
    assert merge_prompts({"dot": [weak], "speck": [strong]}) == [strong]
    assert merge_prompts({"dot": [strong], "speck": [weak]}) == [strong]


def test_box_of_exactly_five_percent_stays_and_one_pixel_more_goes():
    assert is_candidate(box(100, 100, 299, 349))  # 200 x 250 = 5% of 1000 x 1000
    assert not is_candidate(box(100, 100, 300, 349))


@pytest.mark.parametrize(
    "edge", [(0, 50, 20, 70), (50, 0, 70, 20), (979, 50, 999, 70), (50, 979, 70, 999)]
)
def test_box_touching_any_border_is_dropped(edge):
    assert not is_candidate(box(*edge))


def test_box_one_pixel_from_every_border_stays():
    assert is_candidate(box(1, 1, 20, 20))
    assert is_candidate(box(979, 979, 998, 998))


def test_real_crop_drops_the_two_border_boxes():
    assert len(merge_prompts({"dot": fixture("sam_sweep_crop_dot.txt")})) == 29


def test_real_plate_box_does_not_swallow_colonies():
    dish = fixture("sam_variant_5.txt")
    dots = fixture("sam_sweep_full_dot.txt")
    assert max(b.confidence for b in dish) > max(b.confidence for b in dots)
    assert len(merge_prompts({"petri dish": dish, "dot": dots})) == len(dots)


def test_real_prompts_merge_to_69():
    found = {
        prompt: fixture(f"sam_sweep_full_{prompt}.txt") for prompt in ("dot", "speck", "blob")
    }
    merged = merge_prompts(found)
    assert len(merged) == 69
    assert [b.confidence for b in merged] == sorted((b.confidence for b in merged), reverse=True)
    assert not any(same_colony(a, b) for i, a in enumerate(merged) for b in merged[i + 1:])


def test_no_instances_gives_no_colonies():
    assert merge_prompts({"colony": fixture("sam_raw_1.txt")}) == []
