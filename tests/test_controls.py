from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent_commerce.catalog import INJECTION_SENTENCE
from agent_commerce.config import Config
from agent_commerce.errors import ConfigError, ValidationError
from agent_commerce.jsonutil import as_dict, as_int, as_list, as_str, optional_int
from agent_commerce.keys import generate_lab_key
from agent_commerce.ledger import Ledger
from agent_commerce.logging_setup import JsonFormatter, configure, log
from agent_commerce.merchant import LocalMerchant
from agent_commerce.providers.cassette import CassetteProvider
from agent_commerce.providers.fake import FakeProvider
from agent_commerce.providers.types import Completion
from agent_commerce.redact import contains_pan, redact, redact_obj
from agent_commerce.runner import RunRequest, parse_now, run_shopping
from agent_commerce.tools import ToolContext, execute
from agent_commerce.trace import Tracer

NOW = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
PAN = "4242424242424242"


def test_redactor_hides_pan_and_assignments() -> None:
    assert PAN not in redact(f"card {PAN} ok")
    assert "super-secret" not in redact("api_key=super-secret")
    cleaned = redact_obj({"pan": PAN, "note": PAN, "nested": [{"cvv": "123"}]})
    assert isinstance(cleaned, dict)
    assert cleaned["pan"] == "[REDACTED]"
    assert PAN not in json.dumps(cleaned)
    assert contains_pan(PAN)
    assert not contains_pan("3600")


def test_json_formatter_redacts(caplog: pytest.LogCaptureFixture) -> None:
    del caplog
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("agent_commerce.testredact")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        log(logger, logging.INFO, f"saw {PAN}", pan=PAN)
        try:
            raise RuntimeError(PAN)
        except RuntimeError:
            logger.exception("boom")
    finally:
        logger.removeHandler(handler)
    text = stream.getvalue()
    assert PAN not in text
    assert "[REDACTED_PAN]" in text or "[REDACTED]" in text


def test_configure_installs_a_handler() -> None:
    configure("INFO")
    root = logging.getLogger()
    assert root.handlers


def test_json_helpers_fail_closed() -> None:
    with pytest.raises(ValidationError):
        as_dict([])
    with pytest.raises(ValidationError):
        as_dict({1: "x"})
    with pytest.raises(ValidationError):
        as_list({}, "items")
    with pytest.raises(ValidationError):
        as_str("", "name")
    with pytest.raises(ValidationError):
        as_int(True, "n")
    assert optional_int(None, "n") is None
    with pytest.raises(ValidationError):
        optional_int("1", "n")


def test_config_rejects_bad_combinations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_MODE", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert Config.from_env({}).llm_provider == "fake"
    with pytest.raises(ConfigError):
        Config.from_env({"LLM_PROVIDER": "fake", "LIVE_MODE": "1"})
    with pytest.raises(ConfigError):
        Config.from_env({"LLM_PROVIDER": "openai"})
    with pytest.raises(ConfigError):
        Config.from_env({"LLM_PROVIDER": "other"})
    with pytest.raises(ConfigError):
        Config.from_env(
            {
                "LLM_PROVIDER": "openai",
                "LIVE_MODE": "1",
                "LLM_API_KEY": "test-key",
                "LLM_BASE_URL": "not a url",
                "LLM_MODEL": "m",
                "MAX_LIVE_SPEND_USD": "1",
            }
        )
    with pytest.raises(ConfigError):
        Config.from_env({"MERCHANT_HOST": "0.0.0.0"})
    with pytest.raises(ConfigError):
        Config.from_env({"MAX_PAYMENT_ATTEMPTS": "nope"})
    with pytest.raises(ConfigError):
        Config.from_env({"MAX_PAYMENT_ATTEMPTS": "-1"})
    live = Config.from_env(
        {
            "LLM_PROVIDER": "openai",
            "LIVE_MODE": "1",
            "LLM_API_KEY": "test-key",
            "LLM_BASE_URL": "https://llm.example/v1",
            "LLM_MODEL": "lab-model",
            "MAX_LIVE_SPEND_USD": "1.5",
        }
    )
    assert live.live is not None
    assert live.live.max_spend_micro_usd == 1_500_000


def test_tools_refuse_unknown_and_bad_arguments(tmp_path: Path) -> None:
    key = generate_lab_key(tmp_path)
    from agent_commerce.mandate import prepare_mandate

    mandate = prepare_mandate("office", "valid", key.material, NOW)
    ledger = Ledger(tmp_path / "ledger.sqlite")
    ctx = ToolContext(
        mandate=mandate,
        ledger=ledger,
        merchant=LocalMerchant(),
        revoked=False,
        max_attempts=3,
        sleeper=lambda _delay: None,
        rng=__import__("random").Random(0),
        backoff_delays=[],
    )
    assert execute("nope", {}, ctx).error == "unknown_tool"
    assert execute("raise_mandate_cap", {"cap_cents": 1}, ctx).error == "cap_is_not_agent_writable"
    assert execute("add_to_cart", {"sku": "PAPER-A4", "qty": "2"}, ctx).error == "bad_arguments"
    assert execute("request_payment", {"pan": PAN}, ctx).error == "card_data_not_accepted"
    ledger.close()


def test_injection_stays_out_of_the_trace(tmp_path: Path) -> None:
    key = generate_lab_key(tmp_path)
    ledger = Ledger(tmp_path / "ledger.sqlite")
    outcome = run_shopping(
        RunRequest(
            run_id="inj",
            script="ignore_injection",
            mandate_template="office",
            sign_mode="valid",
            now=NOW,
            human="auto",
        ),
        FakeProvider(),
        LocalMerchant(),
        ledger,
        key.material,
        tmp_path,
    )
    ledger.close()
    assert outcome.saw_injection_in_model_context
    assert INJECTION_SENTENCE not in outcome.trace_text
    assert INJECTION_SENTENCE not in outcome.log_text
    assert outcome.spent_cents == 3600
    assert PAN not in outcome.log_text


def test_pan_attack_does_not_charge_or_log_the_number(tmp_path: Path) -> None:
    key = generate_lab_key(tmp_path)
    ledger = Ledger(tmp_path / "ledger.sqlite")
    outcome = run_shopping(
        RunRequest(
            run_id="pan",
            script="pan_attack",
            mandate_template="office",
            sign_mode="valid",
            now=NOW,
            human="auto",
        ),
        FakeProvider(),
        LocalMerchant(),
        ledger,
        key.material,
        tmp_path,
    )
    ledger.close()
    assert outcome.charges == []
    assert PAN not in outcome.log_text
    assert PAN not in outcome.trace_text
    assert key.hex() not in outcome.log_text


def test_cassette_exhaustion_and_max_steps(tmp_path: Path) -> None:
    key = generate_lab_key(tmp_path)
    ledger = Ledger(tmp_path / "ledger.sqlite")
    provider = CassetteProvider(
        (
            Completion(content="", tool_calls=(), tokens_in=1, tokens_out=1),
            Completion(content="", tool_calls=(), tokens_in=1, tokens_out=1),
        )
    )
    # One final turn consumes the first completion. The second is unused.
    outcome = run_shopping(
        RunRequest(
            run_id="short",
            script="buy_paper",
            mandate_template="office",
            sign_mode="valid",
            now=NOW,
            human="auto",
            max_steps=1,
        ),
        provider,
        LocalMerchant(),
        ledger,
        key.material,
        tmp_path,
    )
    assert outcome.status == "completed"
    empty = CassetteProvider(())
    failed = run_shopping(
        RunRequest(
            run_id="empty",
            script="buy_paper",
            mandate_template="office",
            sign_mode="valid",
            now=NOW,
            human="auto",
        ),
        empty,
        LocalMerchant(),
        ledger,
        key.material,
        tmp_path,
    )
    assert failed.status == "failed"
    assert "cassette exhausted" in failed.error
    ledger.close()
    with pytest.raises(Exception, match="UTC"):
        parse_now("2026-10-18")


def test_trace_reads_missing_file(tmp_path: Path) -> None:
    tracer = Tracer(tmp_path, "run")
    assert tracer.read_text() == ""
    tracer.emit("ping", note="ok")
    assert "ping" in tracer.read_text()
