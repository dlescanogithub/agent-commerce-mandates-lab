from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_commerce.catalog import INJECTION_SENTENCE
from agent_commerce.cli import main
from agent_commerce.config import LiveSettings
from agent_commerce.errors import PermanentError, ValidationError
from agent_commerce.evalkit.cases import MIN_CASES, dump_cassette, load_cases, load_cassette
from agent_commerce.evalkit.checks import CHECK_IDS, effect_failures, score_checks
from agent_commerce.evalkit.suite import (
    RecordingProvider,
    _base_config,
    _run_case,
    record_cassettes,
    run_live_guard,
    run_regression,
    run_suite,
)
from agent_commerce.http_merchant import HttpMerchantClient, dispatch, serve
from agent_commerce.ledger import Charge
from agent_commerce.merchant import LocalMerchant
from agent_commerce.providers.live import LiveProvider
from agent_commerce.providers.types import CompletionRequest
from agent_commerce.runner import RunOutcome
from agent_commerce.secretscan import main as scan_main
from agent_commerce.secretscan import scan_repo, scan_text

ROOT = Path(__file__).resolve().parents[1]


def test_suite_passes_and_cassettes_match_the_stub() -> None:
    report = run_suite(ROOT / "evals")
    assert report.ok
    assert report.total >= MIN_CASES
    assert report.passed == report.total
    cases = load_cases(ROOT / "evals" / "cases.json")
    config = _base_config(ROOT / "evals", None)
    for case in cases:
        provider = RecordingProvider()
        result = _run_case(case, provider, config)
        assert result.passed
        text = dump_cassette(case.id, tuple(provider.completions)) + "\n"
        disk = (ROOT / "evals" / "cassettes" / f"{case.id}.json").read_text(encoding="utf-8")
        assert text == disk


def test_regression_fails() -> None:
    report = run_regression(ROOT / "evals")
    assert not report.ok
    assert report.passed == 0
    assert "must stay red" in report.text


def test_live_guard_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_MODE", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert "No request was sent" in run_live_guard()
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LIVE_MODE", "1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_MODEL", "lab-model")
    monkeypatch.setenv("MAX_LIVE_SPEND_USD", "1")
    text = run_live_guard()
    assert "does not send" in text
    assert "No request was sent" in text


def test_rubric_matches_the_checker() -> None:
    rubric = json.loads((ROOT / "evals" / "rubric.json").read_text(encoding="utf-8"))
    assert tuple(rubric["checks"]) == CHECK_IDS


def test_case_loader_rejects_a_bad_file(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_cases(path)
    cassette = tmp_path / "empty.json"
    cassette.write_text('{"completions": []}\n', encoding="utf-8")
    with pytest.raises(ValidationError):
        load_cassette(cassette)


def test_failing_invariants_score_below_one() -> None:
    charge = Charge(
        charge_id="chg",
        idempotency_key="same",
        mandate_id="mnd_office",
        checkout_id="chk-1",
        merchant_id="bazar-inventado",
        amount_cents=50_000,
        currency="USD",
        skus=("GIFT-CARD",),
        categories=("gift_cards",),
        max_unit_cents=50_000,
        approval_id=None,
    )
    outcome = RunOutcome(
        status="completed",
        model_outcome="purchased",
        model_amount=1,
        model_skus=(),
        summary="",
        charges=[charge, charge],
        spent_cents=100_000,
        refunds=0,
        dead_letters=0,
        approvals=0,
        mandate_valid=True,
        mandate_reason="ok",
        cap_cents=1,
        template_cap_cents=20000,
        human_above_cents=5000,
        per_item_max_cents=12000,
        allowed_merchants=("mercado-ficticio",),
        allowed_categories=("office_supplies",),
        tokens_in=0,
        tokens_out=0,
        cost_micro_usd=0,
        error="",
        tool_names=(),
        trace_text="4242424242424242",
        log_text=INJECTION_SENTENCE,
        secret_markers=("deadbeef",),
    )
    cases = load_cases(ROOT / "evals" / "cases.json")
    score = score_checks(cases[0], outcome)
    assert score.score < 1
    assert "spend_within_cap" in score.failures
    assert "no_secret_in_logs" in score.failures
    assert effect_failures(cases[0], outcome)


def test_http_dispatch_and_demo(tmp_path: Path) -> None:
    merchant = LocalMerchant()
    status, body = dispatch(merchant, "GET", "/health", None)
    assert status == 200 and body["ok"] is True
    status, body = dispatch(merchant, "GET", "/missing", None)
    assert status == 404
    status, body = dispatch(merchant, "POST", "/cart", {"sku": "PEN-BLUE", "qty": "1"})
    assert status == 400
    status, body = dispatch(
        merchant, "POST", "/pay", {"checkout_id": "nope", "idempotency_key": "k"}
    )
    assert body["ok"] is False
    with pytest.raises(ValueError):
        serve(merchant, "0.0.0.0", 0)
    assert main(["demo", "--work", str(tmp_path / "demo")]) == 0
    assert (tmp_path / "demo" / "traces").is_dir()


def test_http_client_round_trip() -> None:
    import threading

    merchant = LocalMerchant(faults=["timeout"])
    server = serve(merchant, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        client = HttpMerchantClient(f"http://127.0.0.1:{port}")
        assert client.discovery()["lab"] is True
        assert client.add_to_cart("PEN-BLUE", 1)["ok"] is True
        opened = client.checkout()
        with pytest.raises(TimeoutError):
            client.pay(str(opened["checkout_id"]), "k")
        assert client.order("missing")["ok"] is False
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_live_adapter_parses_a_fake_response_and_refuses_over_cap() -> None:
    settings = LiveSettings(
        api_key="test-key",
        base_url="https://llm.example/v1",
        model="lab-model",
        timeout_s=1,
        max_spend_micro_usd=1,
    )
    seen: list[str] = []

    class _Response:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "ok",
                                "tool_calls": [
                                    {
                                        "id": "c1",
                                        "function": {
                                            "name": "search_catalog",
                                            "arguments": '{"query": "paper"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 4},
                }
            ).encode()

    def opener(http_request: object, timeout: float) -> object:
        del timeout
        full = getattr(http_request, "full_url", "")
        seen.append(str(full))
        return _Response()

    provider = LiveProvider(settings, opener=opener)
    completion = provider.complete(CompletionRequest(messages=({"role": "user", "content": "hi"},)))
    assert completion.tool_calls[0].name == "search_catalog"
    assert completion.tokens_in == 3
    assert seen and seen[0].endswith("/chat/completions")
    provider.spent_micro_usd = 5
    with pytest.raises(PermanentError):
        provider.complete(CompletionRequest(messages=()))


def test_live_adapter_rejects_a_bad_body() -> None:
    settings = LiveSettings(
        api_key="test-key",
        base_url="https://llm.example/v1",
        model="lab-model",
        timeout_s=1,
        max_spend_micro_usd=10,
    )

    class _Response:
        def read(self) -> bytes:
            return b"not-json"

    provider = LiveProvider(settings, opener=lambda _req, _timeout: _Response())
    with pytest.raises(PermanentError):
        provider.complete(CompletionRequest(messages=()))


def test_eval_cli_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_commerce.evalkit.__main__ import main as eval_main

    monkeypatch.chdir(ROOT)
    assert eval_main(["regression"]) == 1
    assert eval_main(["live"]) == 2
    report = tmp_path / "report.json"
    assert eval_main(["run", "--report", str(report)]) == 0
    assert report.exists()


def test_secret_scan_flags_a_private_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert scan_text("hello") == []
    header = "-----BEGIN " + "PRIVATE KEY-----"
    assert scan_text(header + "\nabc") == ["private_key"]
    target = tmp_path / "note.txt"
    target.write_text("ghp_" + ("a" * 20), encoding="utf-8")
    findings = scan_repo(tmp_path)
    assert findings
    monkeypatch.chdir(tmp_path)
    assert scan_main() == 1
    monkeypatch.chdir(ROOT)
    assert scan_main() == 0


def test_record_round_trip(tmp_path: Path) -> None:
    # Copy the golden set and record into a temp directory. CI cassettes stay put.
    source = ROOT / "evals"
    destination = tmp_path / "evals"
    destination.mkdir()
    (destination / "cases.json").write_text(
        (source / "cases.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    record_cassettes(destination)
    assert (destination / "cassettes" / "hp_paper_reams.json").exists()
