"""Whole-image benchmark: SAM prompts + merge against AGAR counts.

Usage: python -m bench.run --split dev --limit 10
"""
import argparse
import json

from bench.split import SPLIT_PATH, load_plates
from platecount.counting import merge_prompts
from platecount.meta.client import MetaClient
from platecount.meta.sam import DEFAULT_PROMPTS, USD_PER_IMAGE, prepare_image, segment

COLUMNS = ("plate", "true", *DEFAULT_PROMPTS, "merged", "nested", "error")


def row(cells: tuple) -> str:
    return " | ".join(f"{cell!s:>6}" for cell in cells)


def main() -> None:
    parser = argparse.ArgumentParser()
    # ponytail: dev only, so a typo can't spend the held-out plates. Add "test" when told to run it.
    parser.add_argument("--split", choices=["dev"], default="dev")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    plate_ids = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))[args.split][: args.limit]
    plates = load_plates()
    client = MetaClient.from_env()
    worst_case = len(plate_ids) * len(DEFAULT_PROMPTS) * USD_PER_IMAGE
    print(f"{len(plate_ids)} {args.split} plates, at most ${worst_case:.4f}")

    print(row(COLUMNS))
    for plate_id in plate_ids:
        plate = plates[plate_id]
        found = segment(client, prepare_image(plate.image))
        merged = merge_prompts(found)
        count = len(merged.colonies)
        print(
            row(
                (
                    plate_id,
                    plate.true_count,
                    *(len(found[prompt]) for prompt in DEFAULT_PROMPTS),
                    count,
                    merged.nested,
                    f"{count - plate.true_count:+d}",
                )
            )
        )
    print(client.cost.summary())


if __name__ == "__main__":
    main()
