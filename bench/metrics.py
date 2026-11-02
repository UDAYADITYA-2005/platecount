"""Count and box accuracy metrics. Pure functions over (found, true) pairs and boxes."""
from collections.abc import Sequence

from pydantic import BaseModel

from platecount.counting import centre_inside, iou, to_image_coords
from platecount.meta.sam import SamInstance

MATCH_IOU = 0.3


class Metrics(BaseModel):
    plates: int
    mae: float
    smape: float  # percent, 0-200
    within_10pct: float  # percent of plates


class BoxScore(BaseModel):
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float | None:
        """None when nothing was predicted: there is no precision to report."""
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        """None when the plate has no labels: there is no recall to report."""
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None


def _can_match(pred: SamInstance, label: SamInstance) -> bool:
    return iou(pred, label) > MATCH_IOU or centre_inside(pred, label) or centre_inside(label, pred)


def match_boxes(
    preds: Sequence[SamInstance], labels: Sequence[SamInstance], width: int, height: int
) -> list[tuple[int, int]]:
    """Pair preds with labels one-to-one, as (pred index, label index), highest IoU first.

    width and height are the labels' image size; each pred is scaled from its own w and h.
    """
    # ponytail: greedy, can miss the maximum matching on crowded plates. Use scipy's
    # linear_sum_assignment if that ever moves the numbers.
    scaled = [to_image_coords(pred, (0, 0, width, height), width, height) for pred in preds]
    candidates = sorted(
        (
            (iou(pred, label), i, j)
            for i, pred in enumerate(scaled)
            for j, label in enumerate(labels)
            if _can_match(pred, label)
        ),
        reverse=True,
    )
    pairs: list[tuple[int, int]] = []
    used_preds: set[int] = set()
    used_labels: set[int] = set()
    for _, i, j in candidates:
        if i not in used_preds and j not in used_labels:
            pairs.append((i, j))
            used_preds.add(i)
            used_labels.add(j)
    return pairs


def score_boxes(
    preds: Sequence[SamInstance], labels: Sequence[SamInstance], width: int, height: int
) -> BoxScore:
    tp = len(match_boxes(preds, labels, width, height))
    return BoxScore(tp=tp, fp=len(preds) - tp, fn=len(labels) - tp)


def pool_scores(scores: Sequence[BoxScore]) -> BoxScore:
    """Add up the plates, so a dense plate weighs more than a sparse one."""
    return BoxScore(
        tp=sum(s.tp for s in scores), fp=sum(s.fp for s in scores), fn=sum(s.fn for s in scores)
    )


def _smape_term(found: int, true: int) -> float:
    """0/0 is a perfect count, so it scores 0 rather than dividing by zero."""
    return 2 * abs(found - true) / (found + true) if found + true else 0.0


def summarize(pairs: Sequence[tuple[int, int]]) -> Metrics:
    """Raises ValueError on no pairs: an average over zero plates is not a number to report."""
    if not pairs:
        raise ValueError("no plates to summarize")
    n = len(pairs)
    return Metrics(
        plates=n,
        mae=sum(abs(found - true) for found, true in pairs) / n,
        smape=100 * sum(_smape_term(found, true) for found, true in pairs) / n,
        within_10pct=100 * sum(abs(found - true) <= 0.1 * true for found, true in pairs) / n,
    )
