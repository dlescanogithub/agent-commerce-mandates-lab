"""Command line. The default path is the local stub and spends nothing."""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_commerce.demo import demo_text, run_demo
from agent_commerce.logging_setup import configure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-commerce")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="buy two reams from the loopback stub")
    demo.add_argument("--work", type=Path, default=Path("var/demo"))
    args = parser.parse_args(argv)
    configure("INFO")
    if args.command == "demo":
        summary = run_demo(args.work)
        print(demo_text(summary))
        return 0 if summary.get("outcome") == "purchased" and summary.get("charges") == 1 else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
