"""HTTP access to the Meta Model API: retries, disk cache and run cost.

The only module that imports httpx.
"""
import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import load_dotenv

URL = "https://api.meta.ai/v1/responses"
MAX_TRIES = 4
TIMEOUT_S = 120
COMPLETED_EVENT = "event: response.completed"


class MetaAPIError(RuntimeError):
    """A Meta API call failed. The message holds the status and response body."""


@dataclass
class RunCost:
    """Running spend for one run. Cache hits are free."""

    usd: float = 0.0
    calls: int = 0
    cache_hits: int = 0

    def summary(self) -> str:
        return f"cost ${self.usd:.4f}: {self.calls} API calls, {self.cache_hits} cache hits"


def cache_key(model: str, prompt: str, image: bytes, options: dict[str, str]) -> str:
    header = json.dumps([model, prompt, options], sort_keys=True).encode("utf-8")
    return hashlib.sha256(header + b"\0" + image).hexdigest()


def completed_response(raw: str) -> dict | None:
    """Return the `response` object of an SSE stream's response.completed event, if any."""
    for line in raw.splitlines():
        if line.startswith("data: {"):
            event = json.loads(line[len("data: "):])
            if event.get("type") == "response.completed":
                return event["response"]
    return None


@dataclass
class MetaClient:
    api_key: str = field(repr=False)
    cache_dir: Path = Path(".cache/meta")
    cost: RunCost = field(default_factory=RunCost)
    transport: httpx.BaseTransport | None = None
    backoff_s: float = 1.0

    @classmethod
    def from_env(cls) -> "MetaClient":
        load_dotenv()
        key = os.environ.get("MODEL_API_KEY")
        if not key:
            raise MetaAPIError("MODEL_API_KEY is not set (check .env)")
        return cls(api_key=key)

    def post_stream(self, key: str, body: dict, cost_usd: float | Callable[[str], float]) -> str:
        """Return the raw SSE text for a request, from the cache when possible.

        cost_usd is a fixed price, or a function of the raw response for token-priced models.
        """
        path = self.cache_dir / f"{key}.txt"
        if path.exists():
            self.cost.cache_hits += 1
            return path.read_text(encoding="utf-8")

        raw = self._post(body)
        self.cost.calls += 1
        self.cost.usd += cost_usd(raw) if callable(cost_usd) else cost_usd

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(raw, encoding="utf-8", newline="")
        os.replace(tmp, path)
        return raw

    def _post(self, body: dict) -> str:
        payload = {**body, "stream": True, "store": False}
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "text/event-stream"}
        failure = ""
        with httpx.Client(transport=self.transport, timeout=TIMEOUT_S) as http:
            for attempt in range(MAX_TRIES):
                if attempt:
                    time.sleep(self.backoff_s * 2 ** (attempt - 1))
                try:
                    r = http.post(URL, json=payload, headers=headers)
                except httpx.TransportError as exc:
                    failure = f"connection error: {exc!r}"
                    continue
                if r.status_code == 200:
                    if COMPLETED_EVENT in r.text:
                        return r.text
                    failure = f"stream ended without response.completed:\n{r.text}"
                elif r.status_code == 429 or r.status_code >= 500:
                    failure = f"HTTP {r.status_code}: {r.text}"
                else:
                    raise MetaAPIError(f"HTTP {r.status_code}: {r.text}")
        raise MetaAPIError(f"gave up after {MAX_TRIES} tries. Last failure: {failure}")
