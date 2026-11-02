"""Precompute the demo plates from the disk cache. Run: python -m scripts.make_samples

Spends nothing: the transport refuses every call, so a cache miss fails loudly. The JSON has
no pixels and is committed. The overlay JPEGs are AGAR images: *.jpg keeps them out of git,
and data.md keeps them out of the repo.
"""
import json
import tempfile
from pathlib import Path

import httpx

from bench.run import NOMINAL_EXPONENT, NOMINAL_ML
from bench.split import load_plates
from platecount.agent.events import EventLog
from platecount.agent.loop import run_agent
from platecount.agent.tools import overlay_jpeg
from platecount.api.app import WEB_DIR, SampleInfo, plate_response
from platecount.meta.client import MetaClient
from platecount.meta.sam import load_image

CREDIT = "AGAR dataset, CC BY-NC 2.0"
NOTE = "AGAR records no dilution, so 10^-2 and 1 mL here are nominal values."
SAMPLES = {"5207": "Sparse plate", "12031": "Medium plate", "518": "Dense plate"}


def refuse(_: httpx.Request) -> httpx.Response:
    return httpx.Response(401, text="cache miss: make_samples never calls the API")


def main() -> None:
    out = WEB_DIR / "samples"
    out.mkdir(exist_ok=True)
    plates = load_plates()
    client = MetaClient(api_key="offline", transport=httpx.MockTransport(refuse))
    for plate_id, label in SAMPLES.items():
        img = load_image(plates[plate_id].image)
        with tempfile.TemporaryDirectory() as folder:
            log = EventLog(Path(folder) / "events.jsonl")
            result = run_agent(client, img, NOMINAL_EXPONENT, NOMINAL_ML, log)
            response = plate_response(None, result, log, [])
        if result.report.status != "verified":
            raise SystemExit(f"{plate_id}: {result.report.status}: {result.report.reason}")
        sample = {
            **response.model_dump(),
            "boxes": [[b.x1, b.y1, b.x2, b.y2] for b in result.boxes],
            "width": img.width,
            "height": img.height,
            "true_count": plates[plate_id].true_count,
            "label": label,
            "credit": CREDIT,
            "note": NOTE,
        }
        (out / f"{plate_id}.json").write_text(json.dumps(sample), encoding="utf-8")
        (out / f"{plate_id}.jpg").write_bytes(overlay_jpeg(img, result.boxes))
        print(plate_id, label, "true", plates[plate_id].true_count, "count", result.report.colonies,
              result.report.steps)
    index = [SampleInfo(id=i, label=label).model_dump() for i, label in SAMPLES.items()]
    (out / "index.json").write_text(json.dumps(index), encoding="utf-8")
    print(client.cost.summary())


if __name__ == "__main__":
    main()
