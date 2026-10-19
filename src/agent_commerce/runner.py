"""One shopping run. The planner proposes. The tools and the ledger decide."""

from __future__ import annotations

import io
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agent_commerce.errors import CommerceError
from agent_commerce.http_merchant import MerchantPort
from agent_commerce.jsonutil import dumps, loads
from agent_commerce.ledger import Charge, Ledger
from agent_commerce.logging_setup import JsonFormatter, log
from agent_commerce.mandate import TEMPLATES, prepare_mandate
from agent_commerce.pricing import cost_micro_usd
from agent_commerce.providers.base import LLMProvider
from agent_commerce.providers.fake import GOALS
from agent_commerce.providers.types import CompletionRequest
from agent_commerce.tools import ToolContext, ToolResult, execute
from agent_commerce.trace import Tracer

LOGGER = logging.getLogger("agent_commerce.run")


@dataclass
class RunRequest:
    run_id: str
    script: str
    mandate_template: str
    sign_mode: str
    now: datetime
    human: str
    faults: tuple[str, ...] = ()
    price_override_cents: int | None = None
    revoke_before_payment: bool = False
    max_steps: int = 12
    max_payment_attempts: int = 3
    key_dir: Path | None = None


@dataclass
class RunOutcome:
    status: str
    model_outcome: str
    model_amount: int | None
    model_skus: tuple[str, ...]
    summary: str
    charges: list[Charge]
    spent_cents: int
    refunds: int
    dead_letters: int
    approvals: int
    mandate_valid: bool
    mandate_reason: str
    cap_cents: int
    template_cap_cents: int
    human_above_cents: int
    per_item_max_cents: int
    allowed_merchants: tuple[str, ...]
    allowed_categories: tuple[str, ...]
    tokens_in: int
    tokens_out: int
    cost_micro_usd: int
    error: str
    tool_names: tuple[str, ...]
    trace_text: str
    log_text: str
    secret_markers: tuple[str, ...]
    backoff_delays: tuple[float, ...] = field(default_factory=tuple)
    saw_injection_in_model_context: bool = False


def run_shopping(
    request: RunRequest,
    provider: LLMProvider,
    merchant: MerchantPort,
    ledger: Ledger,
    key_material: bytes,
    work: Path,
    sleeper: Callable[[float], None] | None = None,
) -> RunOutcome:
    sleep: Callable[[float], None] = _noop if sleeper is None else sleeper
    mandate = prepare_mandate(
        request.mandate_template, request.sign_mode, key_material, request.now
    )
    template = TEMPLATES[request.mandate_template]
    template_cap = int(str(template["cap_cents"]))
    human_above = _template_int(template, "requires_human_above_cents")
    per_item = _template_int(template, "per_item_max_cents")
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    logger = LOGGER
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    tracer = Tracer(work / "traces", request.run_id)
    delays: list[float] = []
    ctx = ToolContext(
        mandate=mandate,
        ledger=ledger,
        merchant=merchant,
        revoked=False,
        max_attempts=request.max_payment_attempts,
        sleeper=sleep,
        rng=random.Random(request.run_id),
        backoff_delays=delays,
    )
    goal = GOALS.get(request.script, request.script)
    messages: list[dict[str, object]] = [
        {
            "role": "user",
            "content": dumps(
                {
                    "goal": goal,
                    "mandate_id": mandate.mandate_id or request.mandate_template,
                    "script": request.script,
                }
            ),
        }
    ]
    tracer.emit(
        "run_started", run_id=request.run_id, script=request.script, mandate_valid=mandate.valid
    )
    log(logger, logging.INFO, "run_started", run_id=request.run_id, script=request.script)
    tokens_in = 0
    tokens_out = 0
    tool_names: list[str] = []
    model_outcome = ""
    model_amount: int | None = None
    model_skus: tuple[str, ...] = ()
    summary = ""
    error = ""
    status = "completed"
    saw_injection = False
    try:
        for _ in range(request.max_steps):
            completion = provider.complete(CompletionRequest(tuple(messages)))
            tokens_in += completion.tokens_in
            tokens_out += completion.tokens_out
            tracer.emit(
                "llm",
                tokens_in=completion.tokens_in,
                tokens_out=completion.tokens_out,
                tool_calls=len(completion.tool_calls),
            )
            if not completion.tool_calls:
                parsed = _parse_final(completion.content)
                model_outcome = parsed[0]
                model_amount = parsed[1]
                model_skus = parsed[2]
                summary = parsed[3]
                messages.append({"role": "assistant", "content": completion.content})
                break
            call = completion.tool_calls[0]
            tool_names.append(call.name)
            if request.revoke_before_payment and call.name == "request_payment":
                ctx.revoked = True
                tracer.emit("mandate_revoked", mandate_id=mandate.mandate_id)
            result = execute(call.name, dict(call.arguments), ctx)
            if result.needs_human:
                result = _human(
                    request.human, ctx, call.name, dict(call.arguments), result, tracer, logger
                )
            if _payload_has_injection(result.payload):
                saw_injection = True
            _log_tool(logger, tracer, call.name, dict(call.arguments), result)
            # The live call is logged before this result exists, and this loop
            # does not call complete() after the last tool. Name and final
            # ok/error only: no arguments and no payload. Other providers
            # do not implement the hook.
            notify = getattr(provider, "note_tool_result", None)
            if callable(notify):
                notify(call.name, result.ok, result.error)
            messages.append(
                {
                    "role": "tool",
                    "name": call.name,
                    "content": dumps(result.payload),
                }
            )
        else:
            status = "failed"
            error = "max_steps"
    except CommerceError as exc:
        status = "failed"
        error = str(exc)
    spent = ledger.spent_cents(mandate.mandate_id) if mandate.mandate_id else 0
    charges = ledger.charges(mandate.mandate_id) if mandate.mandate_id else []
    tracer.emit(
        "run_finished",
        status=status,
        spent_cents=spent,
        charges=len(charges),
        model_outcome=model_outcome,
    )
    log(
        logger,
        logging.INFO,
        "run_finished",
        run_id=request.run_id,
        status=status,
        spent_cents=spent,
    )
    logger.removeHandler(handler)
    logger.propagate = True
    return RunOutcome(
        status=status,
        model_outcome=model_outcome,
        model_amount=model_amount,
        model_skus=model_skus,
        summary=summary,
        charges=charges,
        spent_cents=spent,
        refunds=ledger.refund_count(mandate.mandate_id) if mandate.mandate_id else 0,
        dead_letters=ledger.dead_count(mandate.mandate_id) if mandate.mandate_id else 0,
        approvals=ledger.approval_count("approve"),
        mandate_valid=mandate.valid,
        mandate_reason=mandate.reason,
        cap_cents=mandate.cap_cents,
        template_cap_cents=template_cap,
        human_above_cents=human_above
        if mandate.valid
        else _template_int(template, "requires_human_above_cents"),
        per_item_max_cents=per_item
        if mandate.valid
        else _template_int(template, "per_item_max_cents"),
        allowed_merchants=_strings(template.get("allowed_merchants")),
        allowed_categories=_strings(template.get("allowed_categories")),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_micro_usd=cost_micro_usd(tokens_in, tokens_out),
        error=error,
        tool_names=tuple(tool_names),
        trace_text=tracer.read_text(),
        log_text=buffer.getvalue(),
        secret_markers=(key_material.hex(),),
        backoff_delays=tuple(delays),
        saw_injection_in_model_context=saw_injection,
    )


def _human(
    mode: str,
    ctx: ToolContext,
    name: str,
    arguments: dict[str, object],
    pending: ToolResult,
    tracer: Tracer,
    logger: logging.Logger,
) -> ToolResult:
    checkout_id = pending.payload.get("checkout_id")
    checkout = checkout_id if isinstance(checkout_id, str) else ""
    tracer.emit("human_required", tool=name, checkout_id=checkout)
    log(logger, logging.INFO, "human_required", tool=name, checkout_id=checkout)
    if mode in ("auto", "approve"):
        decision_id = ctx.ledger.record_decision(checkout, "approve")
        tracer.emit("human_decision", decision="approve", decision_id=decision_id)
        log(logger, logging.INFO, "human_decision", decision="approve")
        return execute(name, arguments, ctx)
    if mode == "reject":
        ctx.ledger.record_decision(checkout, "reject")
        tracer.emit("human_decision", decision="reject")
        log(logger, logging.INFO, "human_decision", decision="reject")
        return ToolResult(False, "human_rejected", {"ok": False, "error": "human_rejected"})
    tracer.emit("human_decision", decision="absent")
    log(logger, logging.INFO, "human_decision", decision="absent")
    return ToolResult(False, "human_required", {"ok": False, "error": "human_required"})


def _log_tool(
    logger: logging.Logger,
    tracer: Tracer,
    name: str,
    arguments: dict[str, object],
    result: ToolResult,
) -> None:
    # Arguments go through the redactor. Result bodies do not: they can carry
    # catalog descriptions, and those stay in the model context only.
    log(
        logger,
        logging.INFO,
        "tool_finished",
        tool=name,
        ok=result.ok,
        error=result.error,
        arguments=arguments,
        attempts=result.attempts,
    )
    tracer.emit(
        "tool",
        tool=name,
        ok=result.ok,
        error=result.error,
        attempts=result.attempts,
    )


def _parse_final(content: str) -> tuple[str, int | None, tuple[str, ...], str]:
    try:
        parsed = loads(content)
    except Exception:
        return "", None, (), ""
    if not isinstance(parsed, dict):
        return "", None, (), ""
    outcome = parsed.get("outcome")
    amount = parsed.get("amount_cents")
    skus = parsed.get("skus")
    summary = parsed.get("summary")
    sku_tuple: tuple[str, ...] = ()
    if isinstance(skus, list):
        sku_tuple = tuple(str(item) for item in skus)
    amount_int = amount if isinstance(amount, int) and not isinstance(amount, bool) else None
    return (
        outcome if isinstance(outcome, str) else "",
        amount_int,
        sku_tuple,
        summary if isinstance(summary, str) else "",
    )


def _payload_has_injection(payload: dict[str, object]) -> bool:
    from agent_commerce.catalog import INJECTION_SENTENCE

    return INJECTION_SENTENCE in dumps(payload)


def _template_int(template: dict[str, object], field_name: str) -> int:
    value = template[field_name]
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _noop(_delay: float) -> None:
    return None


def parse_now(value: str) -> datetime:
    if not value.endswith("Z"):
        raise CommerceError("now must be UTC with a Z suffix")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
