"""Load the AGAR sample and freeze the dev/test split.

Run once: `python -m bench.split`. It refuses to replace bench/split.json.
"""
import json
import random
import sys
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

AGAR_ROOT = Path("data/agar_sample/AGAR_representative")
SPLIT_PATH = Path(__file__).with_name("split.json")
SEED = 20261101
DEV_SIZE = 16


class Plate(BaseModel):
    id: str  # filename stem; the JSON's sample_id can disagree (971.json says 972)
    image: Path
    true_count: int


def load_plates(root: Path = AGAR_ROOT) -> dict[str, Plate]:
    """Return scorable plates by id. colonies_number < 0 means AGAR has no count."""
    plates: dict[str, Plate] = {}
    for path in sorted(root.rglob("*.json")):
        count = json.loads(path.read_text(encoding="utf-8"))["colonies_number"]
        if count < 0:
            continue
        if path.stem in plates:
            raise ValueError(f"two plates named {path.stem}: filenames must identify plates")
        plates[path.stem] = Plate(id=path.stem, image=path.with_suffix(".jpg"), true_count=count)
    return plates


def count_band(count: int) -> str:
    if count < 15:
        return "<15"
    if count <= 150:
        return "15-150"
    if count <= 300:
        return "151-300"
    raise ValueError(f"no band for {count} colonies")


def dev_quotas(band_sizes: Mapping[str, int], dev_size: int) -> dict[str, int]:
    """Share dev_size across bands by largest remainder."""
    total = sum(band_sizes.values())
    exact = {band: size * dev_size / total for band, size in band_sizes.items()}
    quotas = {band: int(share) for band, share in exact.items()}
    by_remainder = sorted(exact, key=lambda band: (quotas[band] - exact[band], band))
    for band in by_remainder[: dev_size - sum(quotas.values())]:
        quotas[band] += 1
    return quotas


def make_split(
    plates: Mapping[str, Plate], seed: int = SEED, dev_size: int = DEV_SIZE
) -> dict[str, list[str]]:
    """Stratify by count band. Dev is shuffled, so its first N plates mix the bands."""
    bands: dict[str, list[str]] = {}
    for plate_id in sorted(plates):
        bands.setdefault(count_band(plates[plate_id].true_count), []).append(plate_id)

    quotas = dev_quotas({band: len(ids) for band, ids in bands.items()}, dev_size)
    rng = random.Random(seed)
    dev: list[str] = []
    test: list[str] = []
    for band in sorted(bands):
        ids = bands[band]
        rng.shuffle(ids)
        dev += ids[: quotas[band]]
        test += ids[quotas[band] :]
    rng.shuffle(dev)
    return {"dev": dev, "test": sorted(test)}


def main() -> None:
    if SPLIT_PATH.exists():
        sys.exit(f"{SPLIT_PATH} is frozen; not replacing it")
    split = make_split(load_plates())
    SPLIT_PATH.write_text(json.dumps({"seed": SEED, **split}, indent=2) + "\n", encoding="utf-8")
    print(f"dev {len(split['dev'])}, test {len(split['test'])}, seed {SEED}")


if __name__ == "__main__":
    main()
