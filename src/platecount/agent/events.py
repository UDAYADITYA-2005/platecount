"""Append-only JSONL record of a run. The verifier reads numbers back from this file.

Images are recorded by hash only: visitor photos must never reach a log.
"""
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

EVENTS_DIR = Path("results/raw/events")  # gitignored


class ToolEvent(BaseModel):
    tool: str
    args: str  # exactly as Spark sent them, so malformed calls are on record too
    input_hash: str
    output: dict
    cost_usd: float
    ms: int


def input_hash(image_hash: str, tool: str, args: str) -> str:
    return hashlib.sha256(f"{image_hash}\0{tool}\0{args}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EventLog:
    path: Path

    @classmethod
    def new(cls, name: str, folder: Path = EVENTS_DIR) -> "EventLog":
        """A fresh file per run, so one run's numbers can't vouch for another's."""
        return cls(folder / f"{name}-{uuid.uuid4().hex[:8]}.jsonl")

    def append(self, event: ToolEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")

    def read(self) -> list[ToolEvent]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [ToolEvent.model_validate_json(line) for line in lines]
