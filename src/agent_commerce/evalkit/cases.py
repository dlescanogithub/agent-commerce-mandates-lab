"""Load the golden set. The files are the contract; the runner does not invent cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agent_commerce.errors import ValidationError
from agent_commerce.jsonutil import as_dict, as_int, as_list, as_str, dumps, loads, optional_int
from agent_commerce.providers.types import Completion, ToolCall

MIN_CASES = 30


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    title: str
    script: str
    mandate: str
    sign_mode: str
    now: str
    human: str
    faults: tuple[str, ...]
    price_override_cents: int | None
    revoke_before_payment: bool
    expect_charges: int
    expect_amount_cents: int | None
    expect_refunds: int
    expect_dead_letters: int
    expect_skus: tuple[str, ...]
    expect_outcome: str


def load_cases(path: Path) -> tuple[EvalCase, ...]:
    raw = as_list(loads(path.read_text(encoding="utf-8")), "cases")
    cases = tuple(_case(item) for item in raw)
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValidationError("duplicate eval case id")
    if len(cases) < MIN_CASES:
        raise ValidationError(f"golden set must have at least {MIN_CASES} cases")
    return cases


def load_cassette(path: Path) -> tuple[Completion, ...]:
    payload = as_dict(loads(path.read_text(encoding="utf-8")))
    completions: list[Completion] = []
    for item in as_list(payload.get("completions"), "completions"):
        completions.append(_completion(as_dict(item)))
    if not completions:
        raise ValidationError(f"cassette is empty: {path}")
    return tuple(completions)


def dump_cassette(case_id: str, completions: tuple[Completion, ...]) -> str:
    payload: dict[str, object] = {
        "case_id": case_id,
        "model": "stub-llm-v1",
        "provider": "fake",
        "completions": [_completion_obj(completion) for completion in completions],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _completion(raw: dict[str, object]) -> Completion:
    calls: list[ToolCall] = []
    for item in as_list(raw.get("tool_calls"), "tool_calls"):
        call = as_dict(item)
        arguments = as_dict(call.get("arguments") or {})
        calls.append(
            ToolCall(
                id=as_str(call.get("id"), "id"),
                name=as_str(call.get("name"), "name"),
                arguments=arguments,
            )
        )
    content = raw.get("content")
    return Completion(
        content=content if isinstance(content, str) else "",
        tool_calls=tuple(calls),
        tokens_in=as_int(raw.get("tokens_in"), "tokens_in"),
        tokens_out=as_int(raw.get("tokens_out"), "tokens_out"),
    )


def _completion_obj(completion: Completion) -> dict[str, object]:
    return {
        "content": completion.content,
        "tokens_in": completion.tokens_in,
        "tokens_out": completion.tokens_out,
        "tool_calls": [
            {"arguments": call.arguments, "id": call.id, "name": call.name}
            for call in completion.tool_calls
        ],
    }


def _case(value: object) -> EvalCase:
    raw = as_dict(value)
    category = as_str(raw.get("category"), "category")
    if category not in ("happy", "edge", "adversarial"):
        raise ValidationError(f"bad category on {raw.get('id')}")
    human = as_str(raw.get("human"), "human")
    if human not in ("auto", "approve", "reject", "absent"):
        raise ValidationError("human must be auto, approve, reject, or absent")
    faults = tuple(as_str(item, "faults") for item in as_list(raw.get("faults"), "faults"))
    skus = tuple(
        as_str(item, "expect_skus") for item in as_list(raw.get("expect_skus"), "expect_skus")
    )
    return EvalCase(
        id=as_str(raw.get("id"), "id"),
        category=category,
        title=as_str(raw.get("title"), "title"),
        script=as_str(raw.get("script"), "script"),
        mandate=as_str(raw.get("mandate"), "mandate"),
        sign_mode=as_str(raw.get("sign_mode"), "sign_mode"),
        now=as_str(raw.get("now"), "now"),
        human=human,
        faults=faults,
        price_override_cents=optional_int(raw.get("price_override_cents"), "price_override_cents"),
        revoke_before_payment=raw.get("revoke_before_payment") is True,
        expect_charges=as_int(raw.get("expect_charges"), "expect_charges"),
        expect_amount_cents=optional_int(raw.get("expect_amount_cents"), "expect_amount_cents"),
        expect_refunds=as_int(raw.get("expect_refunds"), "expect_refunds"),
        expect_dead_letters=as_int(raw.get("expect_dead_letters"), "expect_dead_letters"),
        expect_skus=skus,
        expect_outcome=as_str(raw.get("expect_outcome"), "expect_outcome"),
    )


def canonical_case_blob(case: EvalCase) -> str:
    """Stable text used only by tests that want to show a case round-trips."""

    return dumps(
        {
            "id": case.id,
            "script": case.script,
            "expect_outcome": case.expect_outcome,
        }
    )
