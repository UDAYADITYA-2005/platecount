"""One-off: run SAM 3.1 experiments and save the raw responses as test fixtures.

Imports httpx directly because meta/client.py is written from these recordings.
Delete this script once client.py exists.
"""
import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageOps

IMAGE = Path("data/test_plate.jpg")
FIXTURES = Path("tests/fixtures")
URL = "https://api.meta.ai/v1/responses"
OPTIONS = {"include_confidence": "true", "mask_encoding": "one_bit"}
PROMPTS = ["spot", "dot", "white dot", "blob", "speck", "round spot", "bacteria", "mold"]
DENSE_CROP = (700, 880, 1724, 1904)  # picked by eye: about 30 separate colonies
BOXES = [(979, 1026, 1039, 1086), (1354, 868, 1410, 924)]  # in the 2048x1536 frame
BOX_RE = re.compile(r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);[^|]*?(?:c=([\d.]+))?\|>")


def to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def box_prompt(boxes: list[tuple[int, int, int, int]], w: int, h: int) -> str:
    records = [
        f"{i}<|box;x1={x1};y1={y1};x2={x2};y2={y2};w={w};h={h}|>"
        for i, (x1, y1, x2, y2) in enumerate(boxes)
    ]
    return "<0f>" + ",".join(records)


def output_text(raw: str) -> str:
    for line in raw.splitlines():
        if line.startswith("data: {") and '"type":"response.completed"' in line:
            response = json.loads(line[len("data: "):])["response"]
            return "".join(p["text"] for item in response["output"] for p in item["content"])
    raise ValueError(f"no response.completed event in:\n{raw[:2000]}")


def send(jpeg: bytes, text: str, key: str) -> httpx.Response:
    data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    body = {
        "model": "sam-3.1",
        "stream": True,
        "store": False,
        "metadata": OPTIONS,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": text},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
    }
    headers = {"Authorization": f"Bearer {key}", "Accept": "text/event-stream"}
    return httpx.post(URL, json=body, headers=headers, timeout=120)


def run(name: str, label: str, jpeg: bytes, text: str, key: str) -> None:
    start = time.perf_counter()
    r = send(jpeg, text, key)
    elapsed = time.perf_counter() - start
    path = FIXTURES / f"sam_{name}.txt"
    path.write_text(r.text, encoding="utf-8", newline="")
    line = (
        f"{name} | {label} | status {r.status_code} | upload {len(jpeg) / 1024:.1f} KB | "
        f"response {path.stat().st_size / 1024:.1f} KB | {elapsed:.2f} s"
    )
    if r.status_code != 200:
        print(f"{line}\n  body: {r.text[:400]}")
        return
    boxes = BOX_RE.findall(output_text(r.text))
    print(f"{line} | instances {len(boxes)}")
    for x1, y1, x2, y2, c in boxes[:8]:
        print(f"  box {x1},{y1} to {x2},{y2} ({int(x2) - int(x1) + 1}x{int(y2) - int(y1) + 1}) c={c[:4]}")


def main() -> int:
    load_dotenv()
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        print("MODEL_API_KEY is not set (check .env)")
        return 1

    img = ImageOps.exif_transpose(Image.open(IMAGE)).convert("RGB")
    small = img.copy()
    small.thumbnail((2048, 2048))
    full, crop = to_jpeg(small), to_jpeg(img.crop(DENSE_CROP))

    for prompt in PROMPTS:
        slug = prompt.replace(" ", "_")
        run(f"sweep_full_{slug}", prompt, full, prompt, key)
        run(f"sweep_crop_{slug}", prompt, crop, prompt, key)

    boxes = box_prompt(BOXES, small.width, small.height)
    run("box_with_text", "colony + 2 boxes", full, "colony" + boxes, key)
    run("box_only", "2 boxes", full, boxes, key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
