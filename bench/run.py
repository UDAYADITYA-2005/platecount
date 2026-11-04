"""Benchmark: whole-image, tiled, policy and agent counts against AGAR counts and boxes.

Usage: python -m bench.run --split dev --limit 16 --variant agent
"""
import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import NamedTuple

from PIL import Image

from bench.metrics import BoxScore, pool_scores, score_boxes, summarize
from bench.split import SPLIT_PATH, Plate, count_band, load_labels, load_plates
from platecount.agent.events import EventLog
from platecount.agent.loop import run_agent
from platecount.counting import GRID, PlateCount, count_plate, count_tiled, count_whole
from platecount.meta.client import MetaClient
from platecount.meta.sam import DEFAULT_PROMPTS, USD_PER_IMAGE, load_image

BANDS = ("<15", "15-150", "151-300")
MAX_RUN_USD = 5.0  # project rule: a single run must not exceed this without asking
# AGAR records no dilutions. Only the count is scored; these just run the full report path.
NOMINAL_EXPONENT = -2
NOMINAL_ML = 1.0


class PlateResult(NamedTuple):
    true: int
    count: int
    score: BoxScore


VARIANTS: dict[str, Callable[[MetaClient, Image.Image], PlateCount]] = {
    "whole": count_whole,
    "tiled": count_tiled,
    "policy": count_plate,
}
IMAGES_PER_PLATE = {"whole": 1, "tiled": GRID * GRID, "policy": 1 + GRID * GRID}


def row(cells: Sequence) -> str:
    return " | ".join(f"{cell!s:>7}" for cell in cells)


def ratio(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def summary_line(label: str, results: Sequence[PlateResult]) -> str:
    if not results:
        return f"{label}: no plates"
    m = summarize([(r.count, r.true) for r in results])
    score = pool_scores([r.score for r in results])
    return (
        f"{label}: {m.plates} plates, MAE {m.mae:.2f}, sMAPE {m.smape:.1f}%, "
        f"within 10% {m.within_10pct:.1f}%, precision {ratio(score.precision)}, "
        f"recall {ratio(score.recall)}"
    )


def print_summaries(label: str, results: Sequence[PlateResult]) -> None:
    print(f"\n{label}")
    print(summary_line("all", results))
    for band in BANDS:
        print(summary_line(band, [r for r in results if count_band(r.true) == band]))


def score_cells(result: PlateResult) -> list:
    error = f"{result.count - result.true:+d}"
    return [result.count, error, ratio(result.score.precision), ratio(result.score.recall)]


def compare_agent(plate_ids: Sequence[str], plates: Mapping[str, Plate], client: MetaClient) -> None:
    """One row per plate, policy against agent. A rejected plate scores the code's colony set."""
    print(f"{len(plate_ids)} plates, stops if spend passes ${MAX_RUN_USD:.2f}")
    columns = ["count", "err", "prec", "rec"]
    print(row(["plate", "true", *[f"p_{c}" for c in columns], *[f"a_{c}" for c in columns],
               "status", "cost"]), "| tools")
    policy: list[PlateResult] = []
    agent: list[PlateResult] = []
    statuses: list[str] = []
    for plate_id in plate_ids:
        if client.cost.usd > MAX_RUN_USD:
            sys.exit(f"stopped at ${client.cost.usd:.2f}, over the ${MAX_RUN_USD:.2f} run limit")
        plate = plates[plate_id]
        img = load_image(plate.image)
        labels = load_labels(plate, *img.size)
        boxes = count_plate(client, img).merged.colonies
        policy.append(
            PlateResult(plate.true_count, len(boxes), score_boxes(boxes, labels, *img.size))
        )
        result = run_agent(client, img, NOMINAL_EXPONENT, NOMINAL_ML, EventLog.new(plate_id))
        agent.append(
            PlateResult(
                plate.true_count, len(result.boxes), score_boxes(result.boxes, labels, *img.size)
            )
        )
        report = result.report
        statuses.append(report.status)
        cells = [plate_id, plate.true_count, *score_cells(policy[-1]), *score_cells(agent[-1])]
        tools = ",".join(step.removeprefix("segment_") for step in report.steps)
        print(row([*cells, report.status, f"{report.cost_usd:.4f}"]), "|", tools, flush=True)
        if report.status != "verified":
            print(f"  {plate_id}: {report.reason}", flush=True)

    print_summaries("policy", policy)
    print_summaries("agent", agent)
    print(f"\nagent status: {dict(Counter(statuses))}")


def main() -> None:
    parser = argparse.ArgumentParser()
    # ponytail: dev only, so a typo can't spend the held-out plates. Add "test" when told to run it.
    parser.add_argument("--split", choices=["dev"], default="dev")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--variant", choices=[*VARIANTS, "both", "agent"], default="whole")
    args = parser.parse_args()
    client = MetaClient.from_env()
    try:
        run(args, client)
    finally:  # also on the budget stop and on a crash: printed after every run
        print(client.cost.summary())


def run(args: argparse.Namespace, client: MetaClient) -> None:
    variants = ["whole", "tiled"] if args.variant == "both" else [args.variant]
    plate_ids = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))[args.split][: args.limit]
    plates = load_plates()
    if args.variant == "agent":
        compare_agent(plate_ids, plates, client)
        return
    images = len(plate_ids) * sum(IMAGES_PER_PLATE[variant] for variant in variants)
    worst_case = images * len(DEFAULT_PROMPTS) * USD_PER_IMAGE
    print(f"{len(plate_ids)} {args.split} plates, at most ${worst_case:.4f} before cache hits")

    per_variant = (*DEFAULT_PROMPTS, "count", "err", "prec", "rec", "path")
    columns = [f"{v[0]}_{col}" for v in variants for col in per_variant]
    print(row(["plate", "true", *columns]))
    results: dict[str, list[PlateResult]] = {variant: [] for variant in variants}
    for plate_id in plate_ids:
        plate = plates[plate_id]
        img = load_image(plate.image)
        labels = load_labels(plate, *img.size)
        cells: list = [plate_id, plate.true_count]
        for variant in variants:
            counted = VARIANTS[variant](client, img)
            colonies = counted.merged.colonies
            score = score_boxes(colonies, labels, *img.size)
            results[variant].append(PlateResult(plate.true_count, len(colonies), score))
            hits = [counted.prompt_hits[prompt] for prompt in DEFAULT_PROMPTS]
            error = f"{len(colonies) - plate.true_count:+d}"
            cells += [
                *hits, len(colonies), error, ratio(score.precision), ratio(score.recall), counted.path
            ]
        print(row(cells), flush=True)

    for variant in variants:
        print_summaries(variant, results[variant])


if __name__ == "__main__":
    main()
