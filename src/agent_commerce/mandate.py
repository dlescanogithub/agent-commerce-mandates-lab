"""Spending mandate: cap, expiry, merchants, categories, per-item max, human line.

Inspired by the public description of agent payment mandates. This is a lab
HMAC over a canonical JSON body. It is not a verifiable credential, not
SD-JWT, and not a conformant protocol implementation. Verification fails
closed.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from agent_commerce.jsonutil import as_int, as_list, as_str, dumps

SIGNED_FIELDS: tuple[str, ...] = (
    "allowed_categories",
    "allowed_merchants",
    "cap_cents",
    "currency",
    "expires_at",
    "id",
    "nonce",
    "per_item_max_cents",
    "requires_human_above_cents",
    "subject",
)

LAB_CURRENCY = "LAB"


def office_template() -> dict[str, object]:
    """Procurement of office supplies. Amounts are simulated LAB cents."""

    return {
        "id": "mnd_office",
        "subject": "synthetic_buyer_office",
        "cap_cents": 20000,
        "currency": LAB_CURRENCY,
        "expires_at": "2026-12-31T23:59:59Z",
        "allowed_merchants": ["mercado-ficticio"],
        "allowed_categories": ["office_supplies"],
        "per_item_max_cents": 12000,
        "requires_human_above_cents": 5000,
        "nonce": "nonce-office-lab",
    }


def grocery_template() -> dict[str, object]:
    """Household groceries with a weekly cap. A scenario, not a separate product."""

    return {
        "id": "mnd_grocery",
        "subject": "synthetic_household",
        "cap_cents": 10000,
        "currency": LAB_CURRENCY,
        "expires_at": "2026-12-31T23:59:59Z",
        "allowed_merchants": ["mercado-ficticio"],
        "allowed_categories": ["groceries"],
        "per_item_max_cents": 5000,
        "requires_human_above_cents": 4000,
        "nonce": "nonce-grocery-lab",
    }


TEMPLATES: dict[str, dict[str, object]] = {
    "office": office_template(),
    "grocery": grocery_template(),
}


@dataclass(frozen=True)
class Mandate:
    body: dict[str, object]
    signature: str
    valid: bool
    reason: str

    @property
    def cap_cents(self) -> int:
        if not self.valid:
            return 0
        return as_int(self.body["cap_cents"], "cap_cents")

    @property
    def human_above_cents(self) -> int:
        if not self.valid:
            return 0
        return as_int(self.body["requires_human_above_cents"], "requires_human_above_cents")

    @property
    def per_item_max_cents(self) -> int:
        if not self.valid:
            return 0
        return as_int(self.body["per_item_max_cents"], "per_item_max_cents")

    @property
    def mandate_id(self) -> str:
        raw = self.body.get("id")
        return raw if isinstance(raw, str) else ""


def canonical_bytes(body: dict[str, object]) -> bytes:
    payload = {field: body[field] for field in SIGNED_FIELDS}
    return dumps(payload).encode("utf-8")


def sign_mandate(body: dict[str, object], key: bytes) -> str:
    return hmac.new(key, canonical_bytes(body), sha256).hexdigest()


def verify_mandate(body: dict[str, object], signature: str, key: bytes, now: datetime) -> Mandate:
    """Return a mandate that spends nothing unless every check passes."""

    try:
        payload = {field: body[field] for field in SIGNED_FIELDS}
        digest = hmac.new(key, dumps(payload).encode("utf-8"), sha256).hexdigest()
        if not isinstance(signature, str) or not signature:
            return Mandate(body, signature, False, "missing_signature")
        if not hmac.compare_digest(digest, signature):
            return Mandate(body, signature, False, "bad_signature")
        currency = as_str(payload["currency"], "currency")
        if currency != LAB_CURRENCY:
            return Mandate(body, signature, False, "currency")
        cap = as_int(payload["cap_cents"], "cap_cents")
        per_item = as_int(payload["per_item_max_cents"], "per_item_max_cents")
        threshold = as_int(payload["requires_human_above_cents"], "requires_human_above_cents")
        if cap < 1 or per_item < 1 or threshold < 0:
            return Mandate(body, signature, False, "limits")
        merchants = [
            as_str(item, "merchant") for item in as_list(payload["allowed_merchants"], "m")
        ]
        categories = [
            as_str(item, "category") for item in as_list(payload["allowed_categories"], "c")
        ]
        if not merchants or not categories:
            return Mandate(body, signature, False, "allow_list")
        expires = _parse_time(as_str(payload["expires_at"], "expires_at"))
        if now > expires:
            return Mandate(body, signature, False, "expired")
        as_str(payload["id"], "id")
        as_str(payload["subject"], "subject")
        as_str(payload["nonce"], "nonce")
    except (KeyError, TypeError, ValueError):
        return Mandate(body, signature if isinstance(signature, str) else "", False, "malformed")
    return Mandate(dict(payload), signature, True, "ok")


def prepare_mandate(template_name: str, mode: str, key: bytes, now: datetime) -> Mandate:
    """Sign a known template, then optionally break it. ``now`` is the lab clock."""

    if template_name not in TEMPLATES:
        raise ValueError(f"unknown mandate template {template_name}")
    body = dict(TEMPLATES[template_name])
    if mode == "expired":
        body["expires_at"] = "2020-01-01T00:00:00Z"
    signature = sign_mandate(body, key)
    if mode == "tamper_sig":
        signature = ("a" if signature[0] != "a" else "b") + signature[1:]
    elif mode == "tamper_body":
        body["cap_cents"] = as_int(body["cap_cents"], "cap_cents") + 1
    elif mode == "foreign":
        signature = sign_mandate(body, b"foreign-lab-key-not-real-32bytes")
    elif mode == "unsigned":
        signature = ""
    elif mode not in ("valid", "expired"):
        raise ValueError(f"unknown sign mode {mode}")
    return verify_mandate(body, signature, key, now)


def _parse_time(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("time must be UTC with a Z suffix")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
