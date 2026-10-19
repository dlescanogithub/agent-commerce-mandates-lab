"""Redact payment-like and secret-like text before it reaches a log or a trace.

Card numbers in this lab are fake. They are still redacted, so a log line is
safe to paste. The redactor is not a PCI program.
"""

from __future__ import annotations

import re

# 13–19 digits, optional single spaces or dashes. Amounts in this lab are
# small integers, so they do not match. A longer hex token does not match
# either: the pattern requires a word boundary after the digit run.
_PAN = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_SECRET_ASSIGN = re.compile(
    r"(?i)\b(api[_-]?key|authorization|bearer|secret|password)\b\s*[:=]\s*\S+"
)
_SENSITIVE_KEYS = {
    "pan",
    "card",
    "card_number",
    "cvv",
    "cvc",
    "api_key",
    "authorization",
    "secret",
    "password",
    "signature",
    "key",
    "key_hex",
    "hmac_key",
}


def redact(text: str) -> str:
    cleaned = _PAN.sub("[REDACTED_PAN]", text)
    return _SECRET_ASSIGN.sub(lambda match: f"{match.group(1)}=[REDACTED]", cleaned)


def redact_obj(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            if key.lower() in _SENSITIVE_KEYS:
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = redact_obj(item)
        return cleaned
    return value


def contains_pan(text: str) -> bool:
    return _PAN.search(text) is not None
