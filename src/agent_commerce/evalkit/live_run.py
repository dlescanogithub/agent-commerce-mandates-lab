"""One opt-in pass of the golden set against a hosted model.

The runner, tools, mandate, ledger, merchant, and checkers are the cassette
suite's. This module only supplies a live provider. It does not open a socket
until ``LiveProvider`` is constructed with the default opener, which ``make
eval-live`` does only after ``LIVE_ENABLED=1``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from urllib import request as urlrequest

from agent_commerce.config import LiveSettings
from agent_commerce.evalkit.cases import load_cases
from agent_commerce.evalkit.suite import _base_config, _run_case
from agent_commerce.providers.live import LiveProvider, Sleeper

Opener = Callable[[urlrequest.Request, float], object]


def run_eval_live(
    evals_dir: Path,
    settings: LiveSettings,
    *,
    opener: Opener | None = None,
    sleeper: Sleeper | None = None,
    only: tuple[str, ...] | None = None,
) -> int:
    """Run cases until the spend cap. Return 0 only when every started case passed."""

    loaded = load_cases(evals_dir / "cases.json")
    if only is None:
        cases = list(loaded)
    else:
        by_id = {case.id: case for case in loaded}
        cases = [by_id[case_id] for case_id in only if case_id in by_id]
    config = _base_config(evals_dir, None)
    provider = LiveProvider(settings, opener=opener, sleeper=sleeper)
    rows: list[dict[str, object]] = []
    stopped = False
    for case in cases:
        if provider.spent_micro_usd >= settings.max_spend_micro_usd:
            stopped = True
            break
        provider.begin_case(case.id)
        result = _run_case(case, provider, config)
        rows.append(
            {
                "case": result.case_id,
                "category": result.category,
                "check_failures": result.check_failures,
                "deterministic_failures": result.deterministic_failures,
                "passed": result.passed,
            }
        )
    passed = sum(1 for row in rows if row["passed"] is True)
    tool_log = provider.tool_summary()
    summary = {
        "cases": len(rows),
        "model": settings.model,
        "passed": passed,
        "spent_micro_usd": provider.spent_micro_usd,
        "spent_ticks": provider.spent_ticks,
        "stopped_for_spend_cap": stopped,
        "tool_log": tool_log,
    }
    _write_beside_log(settings.log_path, rows, summary)
    print(
        "eval-live: "
        f"{passed}/{len(rows)} passed "
        f"spent_micro_usd={provider.spent_micro_usd} "
        f"stopped_for_spend_cap={str(stopped).lower()}"
    )
    print(
        "tool_log: "
        f"calls={json.dumps(tool_log['tool_calls'], sort_keys=True)} "
        f"rejections={json.dumps(tool_log['tool_rejections'], sort_keys=True)} "
        f"raise_mandate_cap_after_rejection={tool_log['raise_mandate_cap_after_rejection']} "
        f"cases={tool_log['raise_mandate_cap_after_rejection_cases']}"
    )
    if stopped or passed != len(rows) or not rows:
        return 1
    return 0


def _write_beside_log(
    log_path: Path | None,
    rows: list[dict[str, object]],
    summary: dict[str, object],
) -> None:
    if log_path is None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    (log_path.parent / "results.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (log_path.parent / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
