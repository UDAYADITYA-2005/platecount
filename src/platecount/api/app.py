"""The web API over run_agent. Visitor photos stay in memory.

The photo is the raw request body, not multipart: Starlette spools multipart uploads over
1 MB to a temp file on disk. Everything a run writes (SAM cache, event log) goes in a temp
folder deleted when the request ends.
"""
import base64
import io
import json
import logging
import math
import os
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel

from platecount.agent.events import EventLog, ToolEvent
from platecount.agent.loop import AgentResult, Report, run_agent
from platecount.agent.tools import TOOLS, overlay_jpeg
from platecount.meta.client import MetaAPIError, MetaClient

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PHOTO_PIXELS = 24_000_000  # as decoded. Bytes don't bound memory: 0.7 MB of flat 49 MP peaked at 680 MB
MAX_PHOTO_SIDE = 4096  # the largest AGAR plate is 4000 px, so the benchmarked sizes pass unchanged
MAX_IN_LINE = 4  # plates running or waiting; each holds its photo, so at most 40 MB of uploads
PLATES_PER_HOUR = 10
HOUR_S = 3600
RESERVE_USD = 0.25  # held per running plate; the dearest plate so far cost $0.085
MIN_EXPONENT = -12
DEFAULT_EXPONENT = 0
DEFAULT_VOLUME_ML = 1.0
WEB_DIR = Path(__file__).resolve().parents[3] / "web"
SPEND_PATH = Path(".cache/daily_spend.json")  # gitignored
DILUTION_HELP = "Dilution must be a power of ten, such as 10^-2, 1:100 or 0.01."
VOLUME_HELP = "Volume must be a number above 0, in mL."
DEMO_ONLY = "Live counting is off for now. The demo plates below still work."
BUSY = "Several plates are being counted. Please try again in a minute."

FLAG_TEXT = {
    "agent_fallback": "The agent did not finish, so the fixed counting method produced this result.",
    "small_specks": (
        "Some marked objects are much smaller than a typical colony. They are in the count; "
        "check whether they are real colonies."
    ),
    "prompt_disagreement": "The two search prompts found very different numbers. Check this count.",
    "too_many_to_count": "Colonies are too crowded to separate reliably.",
    "spreader": "Growth has spread into a film, which can hide separate colonies. Review this plate.",
    "below_countable_range": "Below the FDA BAM countable range of 15-300 colonies per plate.",
    "above_countable_range": "Above the FDA BAM countable range of 15-300 colonies per plate.",
}

logger = logging.getLogger("platecount.api")


class Flag(BaseModel):
    code: str
    text: str


class Step(BaseModel):
    tool: str
    summary: str
    ms: int
    cost_usd: float


class PlateResponse(BaseModel):
    report: Report
    overlay_jpeg: str  # base64; empty for a demo plate, which has its own overlay route
    flags: list[Flag]
    steps: list[Step]
    assumed: list[str]  # the inputs nobody supplied


class SampleInfo(BaseModel):
    id: str
    label: str


class BadDilution(ValueError):
    """The text is not a power of ten. Its message is safe to show."""


def _power_of_ten(value: Fraction) -> int:
    if value.numerator != 1 or value <= 0:
        raise BadDilution(DILUTION_HELP)
    digits = str(value.denominator)
    if digits != "1" + "0" * (len(digits) - 1):
        raise BadDilution(DILUTION_HELP)
    return 1 - len(digits)


def parse_dilution(text: str) -> int:
    """Return the exponent for "10^-2", "1:100" or "0.01". Exact: no float rounding."""
    text = text.strip()
    try:
        if "^" in text:
            base, power = text.split("^", 1)
            if base.strip() != "10":
                raise BadDilution(DILUTION_HELP)
            exponent = int(power)
        elif ":" in text:
            top, bottom = text.split(":", 1)
            exponent = _power_of_ten(Fraction(int(top), int(bottom)))
        else:
            exponent = _power_of_ten(Fraction(text))
    except (ValueError, ZeroDivisionError) as exc:
        raise BadDilution(DILUTION_HELP) from exc
    if not MIN_EXPONENT <= exponent <= 0:
        raise BadDilution(DILUTION_HELP)
    return exponent


def parse_volume(text: str) -> float:
    try:
        volume = float(text)
    except ValueError as exc:
        raise BadDilution(VOLUME_HELP) from exc
    if not math.isfinite(volume) or volume <= 0:
        raise BadDilution(VOLUME_HELP)
    return volume


def client_ip(request: Request, trust_proxy: bool) -> str:
    """The rate limit key. Never the leftmost X-Forwarded-For: Render keeps what a client sends there.

    Cloudflare, in front of every Render service, sets CF-Connecting-IP itself. The last
    X-Forwarded-For entry comes from the nearest proxy: not forgeable, but it can be shared.
    """
    peer = request.client.host if request.client else "unknown"
    if not trust_proxy:
        return peer
    last_hop = ",".join(request.headers.getlist("x-forwarded-for")).split(",")[-1].strip()
    return request.headers.get("cf-connecting-ip", "").strip() or last_hop or peer


@dataclass
class RateLimit:
    """Plates per visitor per hour, in memory: a restart forgives everyone."""

    hits: dict[str, list[float]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self, visitor: str) -> bool:
        now = time.time()
        with self.lock:
            self.hits = {
                who: live
                for who, times in self.hits.items()
                if (live := [t for t in times if now - t < HOUR_S])
            }
            times = self.hits.setdefault(visitor, [])
            if len(times) >= PLATES_PER_HOUR:
                return False
            times.append(now)
            return True


@dataclass
class SpendCap:
    """Today's spend (UTC), kept on disk so a restart can't reset the cap."""

    path: Path
    limit_usd: float
    reserved_usd: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _spent(self) -> float:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return 0.0
        except ValueError:  # unreadable: assume the worst, spending is the risk
            return self.limit_usd
        return saved["usd"] if saved["date"] == self._today() else 0.0

    def reserve(self) -> bool:
        with self.lock:
            if self._spent() + self.reserved_usd + RESERVE_USD > self.limit_usd:
                return False
            self.reserved_usd += RESERVE_USD
            return True

    def settle(self, cost_usd: float) -> None:
        """Release a reservation and book what the run really cost."""
        with self.lock:
            self.reserved_usd -= RESERVE_USD
            self.path.parent.mkdir(parents=True, exist_ok=True)
            saved = {"date": self._today(), "usd": self._spent() + cost_usd}
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(saved), encoding="utf-8")
            os.replace(tmp, self.path)


def _step_summary(event: ToolEvent) -> str:
    """Built from tool outputs only. Spark's text and error echoes stay out of the page."""
    out = event.output
    if "error" in out:
        return "refused"
    if event.tool in ("segment_whole", "segment_tiled"):
        return f"{out['count']} colonies found"
    if event.tool == "recheck_cell":
        return f"{out['count']} colonies after the recheck, was {out['previous']}"
    if event.tool == "compute_cfu":
        return f"{out['cfu_per_ml']} CFU/mL from {out['colonies']} colonies"
    if event.tool == "flag":
        name = out["flag"].replace("_", " ")
        return f"flagged: {name}" if out["recorded"] else f"{name}: not needed"
    if event.tool == "view_overlay":
        return f"{out['count']} colonies outlined"
    if event.tool == "finish":
        return "sent the result to the verifier"
    if event.tool == "verify":
        return out["reason"]
    return "fixed counting method used"


def event_steps(events: list[ToolEvent]) -> list[Step]:
    return [
        Step(tool=e.tool, summary=_step_summary(e), ms=e.ms, cost_usd=e.cost_usd)
        for e in events
        if e.tool in TOOLS or e.tool in ("verify", "fallback")
    ]


def plate_response(
    img: Image.Image | None, result: AgentResult, log: EventLog, assumed: list[str]
) -> PlateResponse:
    """img None leaves the overlay out, for demo plates whose overlay is a separate file."""
    overlay = "" if img is None else base64.b64encode(overlay_jpeg(img, result.boxes)).decode("ascii")
    return PlateResponse(
        report=result.report,
        overlay_jpeg=overlay,
        flags=[Flag(code=f, text=FLAG_TEXT.get(f, f)) for f in result.report.flags],
        steps=event_steps(log.read()),
        assumed=assumed,
    )


async def _read_photo(request: Request) -> bytes:
    """Read the body, stopping at the limit whatever Content-Length claimed."""
    too_large = HTTPException(413, "The photo must be 10 MB or smaller.")
    if int(request.headers.get("content-length") or 0) > MAX_UPLOAD_BYTES:
        raise too_large
    chunks = bytearray()
    async for chunk in request.stream():
        chunks += chunk
        if len(chunks) > MAX_UPLOAD_BYTES:
            raise too_large
    return bytes(chunks)


def _decode(photo: bytes) -> Image.Image:
    """Upright RGB, at most MAX_PHOTO_SIDE. The size is known before any pixels are decoded.

    draft makes a big JPEG decode at 1/2, 1/4 or 1/8 scale, never below MAX_PHOTO_SIDE // 2.
    It does nothing to other formats, so the pixel check is what bounds those.
    """
    try:
        img = Image.open(io.BytesIO(photo))
        img.draft(None, (MAX_PHOTO_SIDE // 2, MAX_PHOTO_SIDE // 2))
        if img.width * img.height > MAX_PHOTO_PIXELS:
            raise HTTPException(413, "That photo has too many pixels. Use a normal camera photo.")
        img.thumbnail((MAX_PHOTO_SIDE, MAX_PHOTO_SIDE))
        return ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise HTTPException(415, "That file could not be read as a photo. Try a JPEG.") from exc


def env_client() -> MetaClient:
    return MetaClient.from_env()


def create_app(
    client_factory: Callable[[], MetaClient] = env_client,
    spend_path: Path = SPEND_PATH,
    web_dir: Path = WEB_DIR,
) -> FastAPI:
    app = FastAPI(title="PlateCount")
    app.state.limiter = RateLimit()
    app.state.cap = SpendCap(spend_path, float(os.environ.get("DAILY_USD", "3")))
    app.state.trust_proxy = os.environ.get("TRUST_PROXY") == "1"
    app.state.run_lock = threading.Lock()
    app.state.in_line = 0
    samples_dir = web_dir / "samples"

    def sample_list() -> list[SampleInfo]:
        index = samples_dir / "index.json"
        if not index.exists():
            return []
        return [SampleInfo(**s) for s in json.loads(index.read_text(encoding="utf-8"))]

    def sample_file(sample_id: str, name: str) -> Path:
        """The id must come from the index, so it can never be a path."""
        if sample_id not in {s.id for s in sample_list()}:
            raise HTTPException(404, "No such demo plate.")
        path = samples_dir / name
        if not path.exists():
            raise HTTPException(404, "Not available.")
        return path

    def count_photo(
        client: MetaClient, img: Image.Image, exponent: int, volume: float, assumed: list[str]
    ) -> PlateResponse:
        try:
            with tempfile.TemporaryDirectory(prefix="platecount-") as folder:
                client.cache_dir = Path(folder) / "cache"
                log = EventLog(Path(folder) / "events.jsonl")
                return plate_response(img, run_agent(client, img, exponent, volume, log), log, assumed)
        except (MetaAPIError, ValueError) as exc:
            logger.warning("run failed: %s", type(exc).__name__)  # the message may quote a response
            raise HTTPException(502, "The counting service failed. Please try again.") from exc
        finally:
            app.state.cap.settle(client.cost.usd)

    def run_plate(
        photo: bytes, exponent: int, volume: float, assumed: list[str], visitor: str
    ) -> PlateResponse | JSONResponse:
        # ponytail: one plate at a time keeps peak memory at one run on 512 MB, so a second
        # visitor waits about 40 s. Two parallel runs measured 406 MB. Raise with the plan.
        with app.state.run_lock:
            img = _decode(photo)
            try:
                client = client_factory()
            except MetaAPIError:
                return JSONResponse({"detail": DEMO_ONLY, "demo_only": True}, status_code=503)
            if not app.state.limiter.allow(visitor):
                raise HTTPException(429, f"The limit is {PLATES_PER_HOUR} plates an hour. Try again later.")
            if not app.state.cap.reserve():
                return JSONResponse({"detail": DEMO_ONLY, "demo_only": True}, status_code=503)
            return count_photo(client, img, exponent, volume, assumed)

    @app.post("/plates", response_model=PlateResponse)
    async def post_plate(
        request: Request, dilution: str | None = None, volume_ml: str | None = None
    ) -> PlateResponse:
        photo = await _read_photo(request)
        try:
            exponent = parse_dilution(dilution) if dilution else DEFAULT_EXPONENT
            volume = parse_volume(volume_ml) if volume_ml else DEFAULT_VOLUME_ML
        except BadDilution as exc:
            raise HTTPException(422, str(exc)) from exc
        assumed = [
            name for name, given in (("dilution", dilution), ("volume_ml", volume_ml)) if not given
        ]
        if app.state.in_line >= MAX_IN_LINE:
            raise HTTPException(503, BUSY)
        app.state.in_line += 1  # only this event loop touches it, so no lock
        try:
            visitor = client_ip(request, app.state.trust_proxy)
            return await run_in_threadpool(run_plate, photo, exponent, volume, assumed, visitor)
        finally:
            app.state.in_line -= 1

    @app.get("/healthz")
    def healthz(request: Request) -> dict[str, str | bool]:
        """cf_header says whether Render passes CF-Connecting-IP on. It shows no address."""
        return {"status": "ok", "cf_header": "cf-connecting-ip" in request.headers}

    @app.get("/samples", response_model=list[SampleInfo])
    def get_samples() -> list[SampleInfo]:
        return sample_list()

    @app.get("/samples/{sample_id}")
    def get_sample(sample_id: str) -> JSONResponse:
        path = sample_file(sample_id, f"{sample_id}.json")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/samples/{sample_id}/overlay.jpg")
    def get_sample_overlay(sample_id: str) -> FileResponse:
        return FileResponse(sample_file(sample_id, f"{sample_id}.jpg"), media_type="image/jpeg")

    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app


app = create_app()
