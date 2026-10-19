import argparse
import os
from pathlib import Path

from agent_commerce.config import Config, load_live_eval
from agent_commerce.errors import ConfigError
from agent_commerce.evalkit.live_run import run_eval_live
from agent_commerce.evalkit.suite import (
    record_cassettes,
    run_live_guard,
    run_regression,
    run_suite,
    write_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-commerce-eval")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="replay cassettes and fail the process on a regression")
    run.add_argument("--report", type=Path, default=None)
    sub.add_parser("record", help="rewrite cassettes from the fake provider")
    sub.add_parser("regression", help="show the gate blocking a false purchase claim")
    sub.add_parser(
        "live",
        help="refuse a hosted run unless LIVE_MODE=1; this lab does not send either way",
    )
    sub.add_parser(
        "eval-live",
        help="send to a hosted model only when LIVE_ENABLED=1; off by default",
    )
    args = parser.parse_args(argv)
    if args.command == "eval-live":
        return _eval_live()
    evals_dir = Config.from_env().evals_dir
    if args.command == "record":
        record_cassettes(evals_dir)
        print(f"recorded cassettes in {evals_dir / 'cassettes'}")
        return 0
    if args.command == "regression":
        report = run_regression(evals_dir)
        print(report.text)
        return 0 if report.ok else 1
    if args.command == "live":
        print(run_live_guard())
        return 2
    report = run_suite(evals_dir)
    print(report.text)
    write_report(report, args.report or evals_dir / "results" / "latest.json")
    return 0 if report.ok else 1


def _eval_live() -> int:
    if os.environ.get("LIVE_ENABLED", "").strip() != "1":
        print("eval-live is off. Set LIVE_ENABLED=1 to send. No request was sent.")
        return 2
    try:
        settings = load_live_eval(os.environ)
    except ConfigError as exc:
        print(exc)
        return 2
    evals_dir = Path(os.environ.get("EVALS_DIR", "evals"))
    return run_eval_live(evals_dir, settings)


if __name__ == "__main__":
    raise SystemExit(main())
