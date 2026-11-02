"""Benchmark: whole-image, tiled and policy SAM counts against AGAR counts and boxes.

Usage: python -m bench.run --split dev --limit 16 --variant policy
"""
import argparse
import json
from collections.abc import Callable, Sequence
from typing import NamedTuple

from PIL import Image

from bench.metrics import BoxScore, pool_scores, score_boxes, summarize
from bench.split import SPLIT_PATH, count_band, load_labels, load_plates
from platecount.counting import GRID, PlateCount, count_plate, count_tiled, count_whole
from platecount.meta.client import MetaClient
from platecount.meta.sam import DEFAULT_PROMPTS, USD_PER_IMAGE, load_image

BANDS = ("<15", "15-150", "151-300")


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


def main() -> None:
    parser = argparse.ArgumentParser()
    # ponytail: dev only, so a typo can't spend the held-out plates. Add "test" when told to run it.
    parser.add_argument("--split", choices=["dev"], default="dev")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--variant", choices=[*VARIANTS, "both"], default="whole")
    args = parser.parse_args()

    variants = ["whole", "tiled"] if args.variant == "both" else [args.variant]
    plate_ids = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))[args.split][: args.limit]
    plates = load_plates()
    client = MetaClient.from_env()
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
        print(f"\n{variant}")
        print(summary_line("all", results[variant]))
        for band in BANDS:
            subset = [r for r in results[variant] if count_band(r.true) == band]
            print(summary_line(band, subset))
    print(client.cost.summary())


if __name__ == "__main__":
    main()
