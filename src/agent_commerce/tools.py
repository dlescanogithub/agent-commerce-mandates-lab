"""Typed tools. The model proposes. These functions decide.

The amount charged is the checkout total, never a number the model invented.
The idempotency key is derived here. There is no approve tool. Card fields
are refused. A product description is never read as a command.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from agent_commerce.backoff import retry_delay_s
from agent_commerce.catalog import by_sku
from agent_commerce.errors import ValidationError
from agent_commerce.http_merchant import MerchantPort
from agent_commerce.jsonutil import as_int, as_str
from agent_commerce.ledger import Charge, Ledger
from agent_commerce.mandate import LAB_CURRENCY, Mandate

Sleeper = Callable[[float], None]
_CARD_KEYS = {"pan", "card", "card_number", "cvv", "cvc"}


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    error: str
    payload: dict[str, object]
    needs_human: bool = False
    attempts: int = 1


@dataclass
class ToolContext:
    mandate: Mandate
    ledger: Ledger
    merchant: MerchantPort
    revoked: bool
    max_attempts: int
    sleeper: Sleeper
    rng: random.Random
    backoff_delays: list[float]

    def idempotency_key(self, checkout_id: str) -> str:
        return f"{self.mandate.mandate_id}:{checkout_id}"


def execute(name: str, arguments: dict[str, object], ctx: ToolContext) -> ToolResult:
    if _has_card_data(arguments):
        return ToolResult(
            False, "card_data_not_accepted", {"ok": False, "error": "card_data_not_accepted"}
        )
    if name == "discover_merchant":
        return ToolResult(True, "", {"ok": True, "manifest": ctx.merchant.discovery()})
    if name == "search_catalog":
        merchant_id = _text(arguments.get("merchant_id"))
        query = _text(arguments.get("query"))
        return _from_merchant(ctx.merchant.search_catalog(merchant_id, query))
    if name == "add_to_cart":
        return _add(arguments, ctx)
    if name == "checkout":
        refusal = _mandate_open(ctx)
        if refusal is not None:
            return refusal
        return _from_merchant(ctx.merchant.checkout())
    if name == "request_payment":
        return _pay(arguments, ctx)
    if name == "void_or_refund":
        return _refund(ctx)
    if name == "get_order":
        return _from_merchant(ctx.merchant.order(_text(arguments.get("order_id"))))
    if name == "raise_mandate_cap":
        return ToolResult(
            False,
            "cap_is_not_agent_writable",
            {"ok": False, "error": "cap_is_not_agent_writable"},
        )
    return ToolResult(False, "unknown_tool", {"ok": False, "error": "unknown_tool"})


def _add(arguments: dict[str, object], ctx: ToolContext) -> ToolResult:
    refusal = _mandate_open(ctx)
    if refusal is not None:
        return refusal
    try:
        sku = as_str(arguments.get("sku"), "sku")
        qty = as_int(arguments.get("qty"), "qty")
    except ValidationError as exc:
        return ToolResult(False, "bad_arguments", {"ok": False, "error": str(exc)})
    product = by_sku(sku)
    if product is None:
        return ToolResult(False, "unknown_sku", {"ok": False, "error": "unknown_sku"})
    view = {
        "category": product.category,
        "merchant_id": product.merchant_id,
        "sku": product.sku,
        "unit_cents": product.unit_cents,
    }
    reason = _line_allowed(ctx, view, qty)
    if reason is not None:
        return ToolResult(False, reason, {"ok": False, "error": reason, "sku": sku})
    return _from_merchant(ctx.merchant.add_to_cart(sku, qty))


def _pay(arguments: dict[str, object], ctx: ToolContext) -> ToolResult:
    refusal = _mandate_open(ctx)
    if refusal is not None:
        return refusal
    currency = arguments.get("currency")
    if isinstance(currency, str) and currency != LAB_CURRENCY:
        return ToolResult(
            False, "currency_not_allowed", {"ok": False, "error": "currency_not_allowed"}
        )
    order = _current_order(ctx)
    if order is None:
        return ToolResult(False, "no_checkout", {"ok": False, "error": "no_checkout"})
    if order.get("status") == "paid":
        return _replay_paid(ctx, order)
    reason = _order_allowed(ctx, order)
    if reason is not None:
        return ToolResult(False, reason, {"ok": False, "error": reason})
    total = as_int(order.get("total_cents"), "total_cents")
    checkout_id = as_str(order.get("checkout_id"), "checkout_id")
    if total > ctx.mandate.human_above_cents and ctx.ledger.approved(checkout_id) is None:
        return ToolResult(
            False,
            "human_required",
            {
                "ok": False,
                "error": "human_required",
                "checkout_id": checkout_id,
                "amount_cents": total,
            },
            needs_human=True,
        )
    return _charge(ctx, order)


def _charge(ctx: ToolContext, order: dict[str, object]) -> ToolResult:
    checkout_id = as_str(order.get("checkout_id"), "checkout_id")
    key = ctx.idempotency_key(checkout_id)
    existing = ctx.ledger.get_charge(key)
    if existing is not None:
        return _paid_payload(existing, f"ord-{checkout_id}", replayed=True)
    attempts = 0
    last_error = "payment_failed"
    while True:
        attempts += 1
        try:
            result = ctx.merchant.pay(checkout_id, key)
        except TimeoutError:
            result = {"ok": False, "status": 504, "error": "simulated_timeout"}
        if result.get("ok") is True:
            return _record_capture(ctx, order, result, key, attempts)
        status = result.get("status")
        raw_error = result.get("error")
        last_error = raw_error if isinstance(raw_error, str) else "payment_failed"
        retryable = status in (500, 504)
        if retryable and attempts < ctx.max_attempts:
            delay = retry_delay_s(attempts, None, ctx.rng)
            ctx.backoff_delays.append(delay)
            ctx.sleeper(delay)
            continue
        if retryable:
            ctx.ledger.dead_letter(ctx.mandate.mandate_id, checkout_id, last_error, attempts)
            return ToolResult(
                False,
                "dead_letter",
                {"ok": False, "error": "dead_letter", "attempts": attempts},
                attempts=attempts,
            )
        return ToolResult(False, last_error, {"ok": False, "error": last_error}, attempts=attempts)


def _record_capture(
    ctx: ToolContext,
    order: dict[str, object],
    result: dict[str, object],
    key: str,
    attempts: int,
) -> ToolResult:
    checkout_id = as_str(order.get("checkout_id"), "checkout_id")
    lines = _lines(order)
    merchant_raw = lines[0].get("merchant_id") if lines else ""
    merchant_id = merchant_raw if isinstance(merchant_raw, str) else ""
    skus = tuple(str(line.get("sku")) for line in lines)
    categories = tuple(str(line.get("category")) for line in lines)
    units = [line.get("unit_cents") for line in lines]
    max_unit = max(
        (unit for unit in units if isinstance(unit, int) and not isinstance(unit, bool)), default=0
    )
    deliveries = result.get("deliveries")
    charge = Charge(
        charge_id=str(result.get("charge_id")),
        idempotency_key=key,
        mandate_id=ctx.mandate.mandate_id,
        checkout_id=checkout_id,
        merchant_id=merchant_id,
        amount_cents=as_int(result.get("amount_cents"), "amount_cents"),
        currency=LAB_CURRENCY,
        skus=skus,
        categories=categories,
        max_unit_cents=max_unit,
        approval_id=ctx.ledger.approved(checkout_id),
    )
    stored = ctx.ledger.insert_charge(charge)
    return ToolResult(
        True,
        "",
        {
            "ok": True,
            "replayed": bool(result.get("replayed")),
            "charge_id": stored.charge_id,
            "amount_cents": stored.amount_cents,
            "skus": list(stored.skus),
            "order_id": result.get("order_id"),
            "deliveries": deliveries if isinstance(deliveries, int) else 1,
        },
        attempts=attempts,
    )


def _replay_paid(ctx: ToolContext, order: dict[str, object]) -> ToolResult:
    checkout_id = as_str(order.get("checkout_id"), "checkout_id")
    existing = ctx.ledger.get_charge(ctx.idempotency_key(checkout_id))
    if existing is None:
        return ToolResult(False, "already_paid", {"ok": False, "error": "already_paid"})
    order_id = order.get("order_id")
    return _paid_payload(existing, order_id if isinstance(order_id, str) else "", replayed=True)


def _paid_payload(charge: Charge, order_id: str, replayed: bool) -> ToolResult:
    return ToolResult(
        True,
        "",
        {
            "ok": True,
            "replayed": replayed,
            "charge_id": charge.charge_id,
            "amount_cents": charge.amount_cents,
            "skus": list(charge.skus),
            "order_id": order_id,
        },
    )


def _refund(ctx: ToolContext) -> ToolResult:
    refusal = _mandate_open(ctx)
    if refusal is not None:
        return refusal
    charge = ctx.ledger.latest_charge(ctx.mandate.mandate_id)
    if charge is None:
        return ToolResult(False, "no_charge", {"ok": False, "error": "no_charge"})
    result = ctx.merchant.refund(charge.charge_id)
    if result.get("ok") is not True:
        return _from_merchant(result)
    inserted = ctx.ledger.insert_refund(charge.charge_id, charge.amount_cents)
    return ToolResult(
        True,
        "",
        {
            "ok": True,
            "replayed": not inserted,
            "charge_id": charge.charge_id,
            "amount_cents": charge.amount_cents,
            "status": "refunded",
        },
    )


def _current_order(ctx: ToolContext) -> dict[str, object] | None:
    """The lab opens at most one checkout, so the id is stable."""

    found = ctx.merchant.order("ord-chk-1")
    if found.get("ok") is True and isinstance(found.get("checkout_id"), str):
        return found
    return None


def _mandate_open(ctx: ToolContext) -> ToolResult | None:
    if not ctx.mandate.valid:
        reason = ctx.mandate.reason or "mandate_invalid"
        return ToolResult(False, reason, {"ok": False, "error": reason})
    if ctx.revoked:
        return ToolResult(False, "mandate_revoked", {"ok": False, "error": "mandate_revoked"})
    return None


def _line_allowed(ctx: ToolContext, product: dict[str, object], qty: int) -> str | None:
    merchant_id = product.get("merchant_id")
    category = product.get("category")
    unit = product.get("unit_cents")
    if not isinstance(merchant_id, str) or merchant_id not in _allow(ctx, "allowed_merchants"):
        return "merchant_not_allowed"
    if not isinstance(category, str) or category not in _allow(ctx, "allowed_categories"):
        return "category_not_allowed"
    if isinstance(unit, bool) or not isinstance(unit, int):
        return "bad_price"
    if unit > ctx.mandate.per_item_max_cents:
        return "per_item_max"
    if qty < 1:
        return "bad_qty"
    # Lines already in the cart are not in the ledger yet. Payment re-checks
    # the checkout total, which is the binding cap.
    projected = ctx.ledger.spent_cents(ctx.mandate.mandate_id) + (unit * qty)
    if projected > ctx.mandate.cap_cents:
        return "cap_exceeded"
    return None


def _order_allowed(ctx: ToolContext, order: dict[str, object]) -> str | None:
    if order.get("currency") not in (None, LAB_CURRENCY):
        return "currency_not_allowed"
    total = order.get("total_cents")
    if isinstance(total, bool) or not isinstance(total, int):
        return "bad_total"
    if ctx.ledger.spent_cents(ctx.mandate.mandate_id) + total > ctx.mandate.cap_cents:
        return "cap_exceeded"
    for line in _lines(order):
        merchant_id = line.get("merchant_id")
        category = line.get("category")
        unit = line.get("unit_cents")
        if not isinstance(merchant_id, str) or merchant_id not in _allow(ctx, "allowed_merchants"):
            return "merchant_not_allowed"
        if not isinstance(category, str) or category not in _allow(ctx, "allowed_categories"):
            return "category_not_allowed"
        if (
            isinstance(unit, bool)
            or not isinstance(unit, int)
            or unit > ctx.mandate.per_item_max_cents
        ):
            return "per_item_max"
    return None


def _lines(order: dict[str, object]) -> list[dict[str, object]]:
    raw = order.get("lines")
    if not isinstance(raw, list):
        return []
    lines: list[dict[str, object]] = []
    for item in raw:
        if isinstance(item, dict):
            lines.append({str(key): value for key, value in item.items()})
    return lines


def _allow(ctx: ToolContext, field: str) -> set[str]:
    raw = ctx.mandate.body.get(field)
    if not isinstance(raw, list):
        return set()
    return {item for item in raw if isinstance(item, str)}


def _from_merchant(result: dict[str, object]) -> ToolResult:
    if result.get("ok") is True:
        return ToolResult(True, "", result)
    raw = result.get("error")
    error = raw if isinstance(raw, str) and raw else "merchant_error"
    return ToolResult(False, error, result)


def _has_card_data(arguments: dict[str, object]) -> bool:
    return any(key.lower() in _CARD_KEYS for key in arguments)


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""
