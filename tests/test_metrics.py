import pytest

from bench.metrics import BoxScore, match_boxes, pool_scores, score_boxes, summarize
from platecount.meta.sam import SamInstance


def box(x1: int, y1: int, x2: int, y2: int, w: int = 1000, h: int = 1000) -> SamInstance:
    return SamInstance(id=0, x1=x1, y1=y1, x2=x2, y2=y2, w=w, h=h, confidence=0.9, mask="")


def test_same_box_matches():
    assert match_boxes([box(10, 10, 19, 19)], [box(10, 10, 19, 19)], 1000, 1000) == [(0, 0)]


def test_iou_above_threshold_matches_without_a_centre_inside():
    # IoU 49/151 = 0.32. Centres 49.5 and 100.5 each fall just outside the other box.
    assert match_boxes([box(0, 0, 99, 99)], [box(51, 0, 150, 99)], 1000, 1000) == [(0, 0)]


def test_small_box_centred_inside_large_label_matches_on_centre_rule():
    assert match_boxes([box(50, 50, 52, 52)], [box(0, 0, 99, 99)], 1000, 1000) == [(0, 0)]


def test_large_box_around_small_label_matches_on_centre_rule():
    assert match_boxes([box(0, 0, 99, 99)], [box(50, 50, 52, 52)], 1000, 1000) == [(0, 0)]


def test_small_overlap_with_no_centre_inside_does_not_match():
    assert match_boxes([box(0, 0, 9, 9)], [box(8, 8, 17, 17)], 1000, 1000) == []


def test_two_preds_on_one_label_gives_one_match_to_the_better_box():
    preds = [box(12, 10, 21, 19), box(10, 10, 19, 19)]
    assert match_boxes(preds, [box(10, 10, 19, 19)], 1000, 1000) == [(1, 0)]


def test_one_pred_cannot_take_two_labels():
    labels = [box(0, 0, 9, 9), box(10, 0, 19, 9)]
    pairs = match_boxes([box(0, 0, 19, 9)], labels, 1000, 1000)
    assert len(pairs) == 1


def test_pred_from_a_smaller_image_is_scaled_to_the_labels():
    pred = box(50, 50, 99, 99, w=500, h=500)  # 2x: covers 100-199 at full size
    assert match_boxes([pred], [box(100, 100, 199, 199)], 1000, 1000) == [(0, 0)]


def test_unscaled_pred_would_not_have_matched():
    pred = box(50, 50, 99, 99)
    assert match_boxes([pred], [box(100, 100, 199, 199)], 1000, 1000) == []


def test_match_with_nothing_is_empty():
    assert match_boxes([], [box(0, 0, 9, 9)], 1000, 1000) == []
    assert match_boxes([box(0, 0, 9, 9)], [], 1000, 1000) == []


def test_score_boxes_counts_all_three_outcomes():
    preds = [box(0, 0, 9, 9), box(100, 100, 109, 109)]
    labels = [box(0, 0, 9, 9), box(200, 200, 209, 209), box(300, 300, 309, 309)]
    score = score_boxes(preds, labels, 1000, 1000)
    assert score == BoxScore(tp=1, fp=1, fn=2)
    assert score.precision == pytest.approx(0.5)
    assert score.recall == pytest.approx(1 / 3)


def test_precision_and_recall_are_none_when_undefined():
    assert BoxScore(tp=0, fp=0, fn=3).precision is None
    assert BoxScore(tp=0, fp=3, fn=0).recall is None


def test_pool_scores_weights_plates_by_size():
    pooled = pool_scores([BoxScore(tp=1, fp=0, fn=0), BoxScore(tp=0, fp=0, fn=9)])
    assert pooled == BoxScore(tp=1, fp=0, fn=9)
    assert pooled.recall == pytest.approx(0.1)


def test_summarize():
    # errors 0, 10, 20 on true 100, 100, 20
    result = summarize([(100, 100), (110, 100), (40, 20)])
    assert result.plates == 3
    assert result.mae == pytest.approx(10)
    assert result.smape == pytest.approx(100 * (0 + 20 / 210 + 40 / 60) / 3)
    assert result.within_10pct == pytest.approx(200 / 3)


def test_zero_true_zero_found_is_perfect():
    result = summarize([(0, 0)])
    assert result.smape == 0
    assert result.within_10pct == 100


def test_found_on_empty_plate_is_not_within_10pct():
    result = summarize([(3, 0)])
    assert result.smape == 200
    assert result.within_10pct == 0


def test_no_plates_is_an_error():
    with pytest.raises(ValueError):
        summarize([])
