"""One JSONL file per run.

Adapted from the public agent-runtime-evals tracer. String fields are
redacted. Product descriptions, card numbers, and signing keys do not belong
here. See docs/PROVENANCE.md.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent_commerce.redact import redact_obj


class Tracer:
    def __init__(self, directory: Path, run_id: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{run_id}.jsonl"

    def emit(self, event: str, **fields: object) -> None:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
        }
        redacted = redact_obj(fields)
        if isinstance(redacted, dict):
            for key, value in redacted.items():
                if isinstance(key, str):
                    payload[key] = value
        line = json.dumps(payload, sort_keys=True, default=str)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def read_text(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")
