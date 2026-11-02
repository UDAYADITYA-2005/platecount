"""SAM 3.1 segmentation: image preparation, request and response parsing.

Response shape comes from tests/fixtures/sam_sweep_crop_dot.txt. Coordinates are in the
pixels of the uploaded image, so `w` and `h` travel with each instance.
"""
import io
import json
import re
from base64 import b64encode
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps
from pydantic import BaseModel

from platecount.meta.client import MetaClient, cache_key, completed_response

MODEL = "sam-3.1"
USD_PER_IMAGE = 0.0025
MAX_SIDE = 2048
OPTIONS = {"include_confidence": "true", "mask_encoding": "one_bit"}
DEFAULT_PROMPTS = ("dot", "speck")

# Non-greedy: the mask payload is base85, so it can hold ; = and <, but not |.
RECORD = re.compile(r"(\d+)<\|box;(.*?)\|><\|mask;(.*?)\|>")


class SamParseError(ValueError):
    """A SAM response did not have the expected shape. The message holds the raw response."""


class SamInstance(BaseModel):
    id: int
    x1: int
    y1: int
    x2: int
    y2: int
    w: int
    h: int
    confidence: float
    mask: str  # raw token fields, decoded when the outline overlay needs it


class _Part(BaseModel):
    text: str


class _Item(BaseModel):
    content: list[_Part]


class _Response(BaseModel):
    status: str
    output: list[_Item]


def load_image(source: Path | BinaryIO) -> Image.Image:
    """Return the image upright, RGB and at full resolution."""
    return ImageOps.exif_transpose(Image.open(source)).convert("RGB")


def encode_jpeg(img: Image.Image, max_side: int = MAX_SIDE) -> bytes:
    """Return a JPEG with the longest side at most max_side and no EXIF."""
    img = img.copy()
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def prepare_image(path: Path) -> bytes:
    return encode_jpeg(load_image(path))


def _output_text(raw: str) -> str:
    completed = completed_response(raw)
    if completed is None:
        raise SamParseError(f"no response.completed event:\n{raw}")
    response = _Response.model_validate(completed)
    if response.status != "completed":
        raise SamParseError(f"response status {response.status!r}:\n{raw}")
    return "".join(part.text for item in response.output for part in item.content)


def _fields(token: str) -> dict[str, str]:
    return dict(pair.split("=", 1) for pair in token.split(";"))


def parse_stream(raw: str) -> list[SamInstance]:
    """Parse raw SSE text into instances. Zero matches is valid and returns []."""
    try:
        text = _output_text(raw)
        records = RECORD.findall(text)
        if len(records) != text.count("<|box;"):
            raise SamParseError(f"found {len(records)} records in {text.count('<|box;')} boxes:\n{raw}")
        instances = []
        for object_id, box_token, mask_token in records:
            box = _fields(box_token)
            instances.append(
                SamInstance(
                    id=object_id,
                    x1=box["x1"],
                    y1=box["y1"],
                    x2=box["x2"],
                    y2=box["y2"],
                    w=box["w"],
                    h=box["h"],
                    confidence=box["c"],
                    mask=mask_token,
                )
            )
    except SamParseError:
        raise
    except (KeyError, ValueError) as exc:  # pydantic's ValidationError is a ValueError
        raise SamParseError(f"{exc!r} while parsing:\n{raw}") from exc
    return instances


def _request_body(prompt: str, jpeg: bytes) -> dict:
    data_url = "data:image/jpeg;base64," + b64encode(jpeg).decode("ascii")
    return {
        "model": MODEL,
        "metadata": OPTIONS,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
    }


def segment(
    client: MetaClient, jpeg: bytes, prompts: Sequence[str] = DEFAULT_PROMPTS
) -> dict[str, list[SamInstance]]:
    """Run each prompt on the image. Returns instances per prompt, unmerged."""
    return {
        prompt: parse_stream(
            client.post_stream(
                cache_key(MODEL, prompt, jpeg, OPTIONS),
                _request_body(prompt, jpeg),
                USD_PER_IMAGE,
            )
        )
        for prompt in prompts
    }
