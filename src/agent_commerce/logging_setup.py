"""JSON logs on stderr.

Adapted from the public agent-runtime-evals logging helper. This copy runs
every string through the redactor before it is written. See docs/PROVENANCE.md.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import cast

from agent_commerce.redact import redact, redact_obj


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            redacted = redact_obj(dict(extra))
            if isinstance(redacted, dict):
                for key, value in redacted.items():
                    if isinstance(key, str):
                        payload[key] = cast(object, value)
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, sort_keys=True, default=str)


def configure(level: str) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


def log(logger: logging.Logger, level: int, message: str, **fields: object) -> None:
    logger.log(level, message, extra={"extra_fields": fields})
