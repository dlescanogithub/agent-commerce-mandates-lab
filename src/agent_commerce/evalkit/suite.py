"""Replay the golden set. Each case gets a fresh ledger and a fresh lab key."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from agent_commerce import __version__
from agent_commerce.config import Config
from agent_commerce.errors import ConfigError
from agent_commerce.evalkit.cases import EvalCase, dump_cassette, load_cases, load_cassette
from agent_commerce.evalkit.checks import effect_failures, score_checks
from agent_commerce.jsonutil import as_dict, loads
from agent_commerce.keys import generate_lab_key
from agent_commerce.ledger import Ledger
from agent_commerce.merchant import LocalMerchant
from agent_commerce.pricing import MODEL_NAME
from agent_commerce.providers.base import LLMProvider
from agent_commerce.providers.cassette import CassetteProvider
from agent_commerce.providers.fake import FakeProvider
from agent_commerce.providers.types import Completion, CompletionRequest
from agent_commerce.runner import RunOutcome, RunRequest, parse_now, run_shopping

_CATEGORY_ORDER = ("happy", "edge", "adversarial")


@dataclass
class CaseResult:
    case_id: str
    category: str
    passed: bool
    deterministic_failures: list[str]
    check_score: float
    check_failures: list[str]
    tokens_in: int
    tokens_out: int
    cost_micro_usd: int


@dataclass
class SuiteReport:
    ok: bool
    total: int
    passed: int
    failed: int
    tokens_in: int
    tokens_out: int
    cost_micro_usd: int
    check_mean: float
    check_threshold: float
    by_category: dict[str, dict[str, int]]
    results: list[CaseResult]
    text: str


class RecordingProvider:
    """Copies every stub completion so `record` can freeze it."""

    name = "fake"

    def __init__(self) -> None:
        self._inner = FakeProvider()
        self.completions: list[Completion] = []

    def complete(self, request: CompletionRequest) -> Completion:
        completion = self._inner.complete(request)
        self.completions.append(completion)
        return completion


def run_suite(evals_dir: Path, threshold: float | None = None) -> SuiteReport:
    cases = load_cases(evals_dir / "cases.json")
    config = _base_config(evals_dir, threshold)
    results: list[CaseResult] = []
    for case in cases:
        cassette = load_cassette(evals_dir / "cassettes" / f"{case.id}.json")
        results.append(_run_case(case, CassetteProvider(cassette), config))
    return _report(results, config.check_threshold, "cassette replay")


def record_cassettes(evals_dir: Path) -> None:
    cases = load_cases(evals_dir / "cases.json")
    config = _base_config(evals_dir, None)
    destination = evals_dir / "cassettes"
    destination.mkdir(parents=True, exist_ok=True)
    for case in cases:
        provider = RecordingProvider()
        _run_case(case, provider, config)
        text = dump_cassette(case.id, tuple(provider.completions))
        (destination / f"{case.id}.json").write_text(text + "\n", encoding="utf-8")


def run_regression(evals_dir: Path) -> SuiteReport:
    """Replay one hand-written claim that a purchase happened. The ledger is empty."""

    raw = (evals_dir / "regressions" / "false_purchase.json").read_text(encoding="utf-8")
    payload = as_dict(loads(raw))
    case = _case_from_regression(payload)
    cassette = load_cassette(evals_dir / "regressions" / "false_purchase.json")
    config = _base_config(evals_dir, None)
    result = _run_case(case, CassetteProvider(cassette), config)
    report = _report([result], config.check_threshold, "forced regression")
    why = payload.get("why")
    if isinstance(why, str):
        report.text = f"{why}\n{report.text}"
    return report


def run_live_guard() -> str:
    """Refuse a hosted run unless live mode is explicitly configured.

    Even then, this lab does not send. There is no measured live sample.
    """

    try:
        config = Config.from_env()
    except ConfigError as exc:
        return f"{exc} No request was sent."
    if config.live is None:
        return (
            "eval-live requires LIVE_MODE=1 and a hosted LLM_PROVIDER. "
            "CI does not set these. No request was sent. "
            "Measured with a real model: none yet."
        )
    return (
        "Live settings are present, and this lab still does not send. "
        "There is no measured live sample to record. No request was sent."
    )


def write_report(report: SuiteReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "by_category": report.by_category,
        "check_mean": report.check_mean,
        "check_threshold": report.check_threshold,
        "cost_micro_usd": report.cost_micro_usd,
        "failed": report.failed,
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "model": MODEL_NAME,
        "passed": report.passed,
        "provider": "cassette",
        "tokens_in": report.tokens_in,
        "tokens_out": report.tokens_out,
        "total": report.total,
        "version": __version__,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_case(case: EvalCase, provider: LLMProvider, config: Config) -> CaseResult:
    with tempfile.TemporaryDirectory(prefix="mandate-eval-") as temporary:
        work = Path(temporary)
        key = generate_lab_key(work / "keys")
        ledger = Ledger(work / "ledger.sqlite")
        merchant = LocalMerchant(
            faults=list(case.faults),
            price_override_cents=case.price_override_cents,
        )
        request = RunRequest(
            run_id=case.id,
            script=case.script,
            mandate_template=case.mandate,
            sign_mode=case.sign_mode,
            now=parse_now(case.now),
            human=case.human,
            faults=case.faults,
            price_override_cents=case.price_override_cents,
            revoke_before_payment=case.revoke_before_payment,
            max_steps=config.max_agent_steps,
            max_payment_attempts=config.max_payment_attempts,
        )
        try:
            outcome = run_shopping(request, provider, merchant, ledger, key.material, work)
        finally:
            ledger.close()
            key.close()
    return _result(case, outcome, config.check_threshold)


def _result(case: EvalCase, outcome: RunOutcome, threshold: float) -> CaseResult:
    checked = score_checks(case, outcome)
    failures = effect_failures(case, outcome)
    passed = not failures and checked.score + 1e-9 >= threshold
    return CaseResult(
        case_id=case.id,
        category=case.category,
        passed=passed,
        deterministic_failures=failures,
        check_score=checked.score,
        check_failures=list(checked.failures),
        tokens_in=outcome.tokens_in,
        tokens_out=outcome.tokens_out,
        cost_micro_usd=outcome.cost_micro_usd,
    )


def _case_from_regression(payload: dict[str, object]) -> EvalCase:
    raw = as_dict(payload.get("case"))
    # Reuse the golden-set parser by wrapping a one-element list.
    from agent_commerce.evalkit.cases import _case

    return _case(raw)


def _report(results: list[CaseResult], threshold: float, label: str) -> SuiteReport:
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    tokens_in = sum(result.tokens_in for result in results)
    tokens_out = sum(result.tokens_out for result in results)
    cost = sum(result.cost_micro_usd for result in results)
    scores = [result.check_score for result in results]
    mean = sum(scores) / len(scores) if scores else 0.0
    by_category: dict[str, dict[str, int]] = {}
    for category in _CATEGORY_ORDER:
        group = [result for result in results if result.category == category]
        if not group:
            continue
        by_category[category] = {
            "passed": sum(1 for result in group if result.passed),
            "total": len(group),
        }
    ok = passed == total and total > 0 and mean + 1e-9 >= threshold
    lines = [
        (
            f"eval gate ({label}): {'PASS' if ok else 'FAIL'} {passed}/{total} "
            f"check_mean={mean:.2f} threshold={threshold:.2f}"
        ),
        f"tokens_in={tokens_in} tokens_out={tokens_out} cost_micro_usd={cost}",
    ]
    for result in results:
        flag = "pass" if result.passed else "FAIL"
        lines.append(f"{flag} {result.case_id} {result.category} check={result.check_score:.2f}")
        for failure in result.deterministic_failures:
            lines.append(f"  deterministic {failure}")
        for failure in result.check_failures:
            lines.append(f"  check {failure}")
    return SuiteReport(
        ok=ok,
        total=total,
        passed=passed,
        failed=total - passed,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_micro_usd=cost,
        check_mean=mean,
        check_threshold=threshold,
        by_category=by_category,
        results=results,
        text="\n".join(lines),
    )


def _base_config(evals_dir: Path, threshold: float | None) -> Config:
    config = Config.from_env({})
    if threshold is None:
        threshold = config.check_threshold
    return replace(config, evals_dir=evals_dir, check_threshold=threshold)
