"""One local purchase against the loopback merchant. No key, no spend."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from agent_commerce.http_merchant import HttpMerchantClient, serve
from agent_commerce.keys import generate_lab_key
from agent_commerce.ledger import Ledger
from agent_commerce.merchant import LocalMerchant
from agent_commerce.providers.fake import FakeProvider
from agent_commerce.runner import RunRequest, parse_now, run_shopping


def run_demo(work: Path, host: str = "127.0.0.1") -> dict[str, object]:
    """Buy two reams through the HTTP stub and return a JSON-ready summary."""

    work.mkdir(parents=True, exist_ok=True)
    merchant = LocalMerchant()
    server = serve(merchant, host, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        client = HttpMerchantClient(f"http://{host}:{port}")
        manifest = client.discovery()
        key = generate_lab_key(work / "keys")
        ledger = Ledger(work / "ledger.sqlite")
        try:
            outcome = run_shopping(
                RunRequest(
                    run_id="demo-paper",
                    script="buy_paper",
                    mandate_template="office",
                    sign_mode="valid",
                    now=parse_now("2026-10-18T15:00:00Z"),
                    human="auto",
                    max_steps=12,
                    max_payment_attempts=3,
                ),
                FakeProvider(),
                client,
                ledger,
                key.material,
                work,
            )
        finally:
            ledger.close()
            key.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    return {
        "lab": True,
        "not_real_payment": True,
        "merchant_manifest_lab": manifest.get("lab") is True,
        "merchants": _merchant_names(manifest),
        "outcome": outcome.model_outcome,
        "amount_cents": outcome.charges[0].amount_cents if outcome.charges else 0,
        "currency": "LAB",
        "charges": len(outcome.charges),
        "spent_cents": outcome.spent_cents,
        "human_approvals": outcome.approvals,
        "mandate_valid": outcome.mandate_valid,
        "tokens_in": outcome.tokens_in,
        "tokens_out": outcome.tokens_out,
        "cost_micro_usd": outcome.cost_micro_usd,
        "summary": outcome.summary,
    }


def demo_text(summary: dict[str, object]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True)


def _merchant_names(manifest: dict[str, object]) -> list[object]:
    raw = manifest.get("merchants")
    if not isinstance(raw, list):
        return []
    names: list[object] = []
    for item in raw:
        if isinstance(item, dict):
            names.append(item.get("display_name"))
    return names
