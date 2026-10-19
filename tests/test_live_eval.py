"""Offline tests for the live adapter. No socket."""

from __future__ import annotations

import io
import json
import random
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

import pytest

from agent_commerce.config import DEFAULT_LIVE_MODEL, LiveSettings, load_live_eval
from agent_commerce.errors import ConfigError, PermanentError
from agent_commerce.evalkit.live_run import run_eval_live
from agent_commerce.keys import generate_lab_key
from agent_commerce.ledger import Ledger
from agent_commerce.merchant import LocalMerchant
from agent_commerce.providers.live import SYSTEM_PROMPT, LiveProvider, tool_schemas
from agent_commerce.providers.types import CompletionRequest
from agent_commerce.runner import RunRequest, parse_now, run_shopping
from agent_commerce.tools import ToolContext, execute

ROOT = Path(__file__).resolve().parents[1]
_KEY = "lab-live-key"
_NOW = "2026-10-18T15:00:00Z"


def test_empty_key_does_not_call(tmp_path: Path) -> None:
    def opener(_req: object, _timeout: float) -> object:
        raise AssertionError("opener called")

    with pytest.raises(ConfigError, match="empty"):
        LiveProvider(_settings(tmp_path / "calls.jsonl", api_key=" "), opener=opener)


def test_spend_cap_blocks_before_the_next_request(tmp_path: Path) -> None:
    calls: list[int] = []

    def opener(_req: object, _timeout: float) -> object:
        calls.append(1)
        return _Response(_final_payload(ticks=20_000))

    log = tmp_path / "calls.jsonl"
    provider = LiveProvider(
        _settings(log, max_spend_micro_usd=1),
        opener=opener,
        sleeper=lambda _delay: None,
    )
    provider.begin_case("hp_paper_reams")
    provider.complete(_user("buy paper"))
    with pytest.raises(PermanentError, match="MAX_LIVE_SPEND_USD"):
        provider.complete(_user("again"))
    assert calls == [1]
    text = log.read_text(encoding="utf-8")
    assert "spend_cap" in text
    assert _KEY not in text
    assert "buy paper" not in text
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[-1]["record"] == "model_call"
    assert rows[-1]["error"] == "spend_cap"
    assert rows[-1]["tool_calls_names"] == []
    assert rows[-1]["step"] is None


def test_http_error_is_logged_without_the_key_and_retried(tmp_path: Path) -> None:
    calls: list[int] = []
    delays: list[float] = []

    def opener(_req: object, _timeout: float) -> object:
        calls.append(1)
        if len(calls) == 1:
            raise urlerror.HTTPError(
                "https://llm.example/v1/chat/completions",
                500,
                "err",
                hdrs=None,
                fp=io.BytesIO(f'{{"detail":"{_KEY}"}}'.encode()),
            )
        return _Response(_final_payload(ticks=0))

    log = tmp_path / "calls.jsonl"
    provider = LiveProvider(
        _settings(log, max_http_attempts=2),
        opener=opener,
        sleeper=delays.append,
    )
    completion = provider.complete(_user("hello goal"))
    assert completion.content.startswith("{")
    assert len(calls) == 2
    assert delays
    text = log.read_text(encoding="utf-8")
    assert _KEY not in text
    assert "hello goal" not in text
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[0]["http_status"] == 500
    assert rows[1]["http_status"] == 200


def test_client_error_is_not_retried(tmp_path: Path) -> None:
    calls: list[int] = []

    def opener(_req: object, _timeout: float) -> object:
        calls.append(1)
        raise urlerror.HTTPError(
            "https://llm.example/v1/chat/completions",
            401,
            "no",
            hdrs=None,
            fp=io.BytesIO(b"unauthorized"),
        )

    provider = LiveProvider(
        _settings(tmp_path / "calls.jsonl", max_http_attempts=2),
        opener=opener,
        sleeper=lambda _delay: pytest.fail("slept"),
    )
    with pytest.raises(PermanentError, match="live http 401"):
        provider.complete(_user("x"))
    assert calls == [1]


def test_tool_call_schema_history_and_bad_arguments(tmp_path: Path) -> None:
    bodies: list[dict[str, object]] = []

    def opener(http_request: object, _timeout: float) -> object:
        raw = getattr(http_request, "data", b"")
        assert isinstance(raw, bytes)
        bodies.append(json.loads(raw.decode("utf-8")))
        if len(bodies) == 1:
            return _Response(_tool_payload("not-json"))
        return _Response(_final_payload(ticks=0))

    provider = LiveProvider(
        _settings(tmp_path / "calls.jsonl"),
        opener=opener,
        sleeper=lambda _delay: None,
    )
    provider.begin_case("hp_pens")
    first = provider.complete(_user("pens"))
    assert first.tool_calls[0].name == "search_catalog"
    assert first.tool_calls[0].arguments == {}
    second = provider.complete(
        CompletionRequest(
            messages=(
                {"role": "user", "content": "pens"},
                {"role": "tool", "name": "search_catalog", "content": '{"ok": true}'},
            )
        )
    )
    assert second.tool_calls == ()
    assert "discovered" in second.content
    sent = bodies[0]
    tools = sent["tools"]
    assert isinstance(tools, list)
    names = [item["function"]["name"] for item in tools if isinstance(item, dict)]
    assert names[-1] == "raise_mandate_cap"
    assert len(names) == 8
    assert sent["parallel_tool_calls"] is False
    assert sent["tool_choice"] == "auto"
    history = bodies[1]["messages"]
    assert isinstance(history, list)
    assert history[0]["content"] == SYSTEM_PROMPT
    assert history[-1]["role"] == "tool"
    assert history[-1]["tool_call_id"] == "c1"
    assert _KEY not in json.dumps(sent)


def test_configured_price_is_dated_and_unknown_cost_stops(tmp_path: Path) -> None:
    def opener(_req: object, _timeout: float) -> object:
        return _Response(
            {
                "choices": [{"message": {"content": '{"outcome":"refused","skus":[]}'}}],
                "usage": {"prompt_tokens": 1_000, "completion_tokens": 0},
            }
        )

    log = tmp_path / "priced.jsonl"
    provider = LiveProvider(
        _settings(
            log,
            max_spend_micro_usd=500,
            input_usd_per_million=1.0,
            output_usd_per_million=2.0,
            price_date="2026-10-18",
        ),
        opener=opener,
        sleeper=lambda _delay: None,
    )
    provider.complete(_user("priced"))
    row = json.loads(log.read_text(encoding="utf-8"))
    assert row["cost_source"] == "configured_token_price"
    assert row["price_date"] == "2026-10-18"
    assert row["cost_micro_usd"] == 1000
    assert provider.spent_micro_usd == 1000
    with pytest.raises(PermanentError, match="MAX_LIVE_SPEND_USD"):
        provider.complete(_user("next"))


def test_timeout_and_bad_json(tmp_path: Path) -> None:
    calls: list[str] = []

    def opener(_req: object, _timeout: float) -> object:
        calls.append("t")
        if len(calls) == 1:
            raise TimeoutError
        return _Response(b"not-json")

    provider = LiveProvider(
        _settings(tmp_path / "calls.jsonl", max_http_attempts=2),
        opener=opener,
        sleeper=lambda _delay: None,
    )
    with pytest.raises(PermanentError, match="live http 200"):
        provider.complete(_user("z"))
    text = (tmp_path / "calls.jsonl").read_text(encoding="utf-8")
    assert '"error": "timeout"' in text or '"error": "timeout"' in text.replace(" ", "")
    assert "not_json" in text


def test_max_steps_loop_spends_nothing(tmp_path: Path) -> None:
    def opener(_req: object, _timeout: float) -> object:
        return _Response(_tool_payload("{}"))

    key = generate_lab_key(tmp_path)
    ledger = Ledger(tmp_path / "ledger.sqlite")
    provider = LiveProvider(
        _settings(tmp_path / "calls.jsonl", max_spend_micro_usd=5_000_000),
        opener=opener,
        sleeper=lambda _delay: None,
    )
    provider.begin_case("edge_expired")
    try:
        outcome = run_shopping(
            RunRequest(
                run_id="edge_expired",
                script="buy_paper",
                mandate_template="office",
                sign_mode="valid",
                now=parse_now(_NOW),
                human="auto",
                max_steps=2,
                max_payment_attempts=3,
            ),
            provider,
            LocalMerchant(),
            ledger,
            key.material,
            tmp_path,
        )
    finally:
        ledger.close()
        key.close()
    assert outcome.status == "failed"
    assert outcome.error == "max_steps"
    assert outcome.charges == []
    assert outcome.spent_cents == 0
    assert outcome.summary == ""
    rows = [
        json.loads(line)
        for line in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["record"] for row in rows] == [
        "model_call",
        "tool_result",
        "model_call",
        "tool_result",
    ]
    assert rows[0]["tool_calls_names"] == ["search_catalog", "raise_mandate_cap"]
    assert rows[1]["tool"] == "search_catalog"
    assert rows[1]["status"] == "rejected"
    assert rows[1]["code"] == "unknown_merchant"
    assert rows[1]["step"] == 1
    assert rows[1]["index"] == 0
    summary = provider.tool_summary()
    assert summary["tool_calls"] == {"raise_mandate_cap": 2, "search_catalog": 2}
    assert summary["tool_rejections"] == {"search_catalog": 2}
    assert summary["raise_mandate_cap_after_rejection"] == 1
    assert summary["raise_mandate_cap_after_rejection_cases"] == 1


def test_raise_mandate_cap_schema_is_refused_by_the_tool(tmp_path: Path) -> None:
    descriptions = []
    for item in tool_schemas():
        function = item["function"]
        assert isinstance(function, dict)
        if function["name"] == "raise_mandate_cap":
            descriptions.append(str(function["description"]))
    assert descriptions
    assert "not agent-writable" in descriptions[0]
    key = generate_lab_key(tmp_path)
    from agent_commerce.mandate import prepare_mandate

    mandate = prepare_mandate("office", "valid", key.material, parse_now(_NOW))
    ledger = Ledger(tmp_path / "ledger.sqlite")
    try:
        result = execute(
            "raise_mandate_cap",
            {"cap_cents": 999_999},
            ToolContext(
                mandate=mandate,
                ledger=ledger,
                merchant=LocalMerchant(),
                revoked=False,
                max_attempts=3,
                sleeper=lambda _delay: None,
                rng=random.Random(0),
                backoff_delays=[],
            ),
        )
    finally:
        ledger.close()
        key.close()
    assert result.error == "cap_is_not_agent_writable"


def test_load_live_eval_defaults_and_hides_the_key() -> None:
    with pytest.raises(ConfigError, match="LIVE_ENABLED"):
        load_live_eval({})
    with pytest.raises(ConfigError, match="XAI_API_KEY"):
        load_live_eval({"LIVE_ENABLED": "1"})
    settings = load_live_eval(
        {
            "LIVE_ENABLED": "1",
            "XAI_API_KEY": _KEY,
            "MAX_LIVE_SPEND_USD": "0.30",
        }
    )
    assert settings.model == DEFAULT_LIVE_MODEL
    assert settings.base_url == "https://api.x.ai/v1"
    assert settings.max_spend_micro_usd == 300_000
    assert _KEY not in repr(settings)
    with pytest.raises(ConfigError, match="together"):
        load_live_eval(
            {
                "LIVE_ENABLED": "1",
                "XAI_API_KEY": _KEY,
                "MAX_LIVE_SPEND_USD": "0.30",
                "LIVE_INPUT_USD_PER_MILLION": "1",
            }
        )


def test_eval_live_command_stays_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_commerce.evalkit.__main__ import main as eval_main

    def boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("socket opened")

    monkeypatch.setattr(urlrequest, "urlopen", boom)
    monkeypatch.delenv("LIVE_ENABLED", raising=False)
    assert eval_main(["eval-live"]) == 2
    monkeypatch.setenv("LIVE_ENABLED", "1")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert eval_main(["eval-live"]) == 2


def test_harness_one_case_and_spend_stop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[int] = []

    def opener(_req: object, _timeout: float) -> object:
        calls.append(1)
        ticks = 20_000 if len(calls) == 1 else 0
        return _Response(_final_payload(ticks=ticks, outcome="discovered"))

    code = run_eval_live(
        ROOT / "evals",
        _settings(tmp_path / "calls.jsonl", max_spend_micro_usd=1),
        opener=opener,
        sleeper=lambda _delay: None,
        only=("hp_discovery", "hp_pens"),
    )
    assert code == 1
    assert calls == [1]
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["stopped_for_spend_cap"] is True
    assert summary["passed"] == 1
    assert summary["tool_log"] == {
        "raise_mandate_cap_after_rejection": 0,
        "raise_mandate_cap_after_rejection_cases": 0,
        "tool_calls": {},
        "tool_rejections": {},
    }
    printed = capsys.readouterr().out
    assert "raise_mandate_cap_after_rejection=0" in printed
    assert "cases=0" in printed
    assert _KEY not in (tmp_path / "calls.jsonl").read_text(encoding="utf-8")


def test_tool_log_hides_arguments_and_counts_raise_after_rejection(tmp_path: Path) -> None:
    pan = "4242424242424242"
    sentinel = "free-text-sentinel-q7"
    leaked = {"note": pan, "blob": _KEY, "memo": sentinel}
    scripted = [
        _named_tools(
            [
                ("add_to_cart", {"sku": "NOT-A-SKU", "qty": 1, **leaked}),
                ("raise_mandate_cap", {"cap_cents": 9, **leaked}),
            ]
        ),
        _named_tools([("raise_mandate_cap", {"cap_cents": 9, **leaked})]),
        _final_payload(ticks=0, outcome="refused"),
        _named_tools([("discover_merchant", {"merchant_id": "mercado-ficticio", **leaked})]),
        _named_tools([("raise_mandate_cap", {"cap_cents": 1, **leaked})]),
        _final_payload(ticks=0, outcome="discovered"),
    ]
    cursor = {"n": 0}

    def opener(_req: object, _timeout: float) -> object:
        payload = scripted[cursor["n"]]
        cursor["n"] += 1
        return _Response(payload)

    log = tmp_path / "calls.jsonl"
    provider = LiveProvider(_settings(log), opener=opener, sleeper=lambda _delay: None)
    key = generate_lab_key(tmp_path)
    try:
        _one_shop(tmp_path, provider, key.material, "case_after_reject")
        _one_shop(tmp_path, provider, key.material, "case_raise_first")
    finally:
        key.close()

    text = log.read_text(encoding="utf-8")
    assert pan not in text
    assert "[REDACTED_PAN]" not in text
    assert _KEY not in text
    assert sentinel not in text
    assert "NOT-A-SKU" not in text
    assert "mercado-ficticio" not in text
    assert "cap_cents" not in text
    assert "Buy 2 reams" not in text
    assert '"arguments"' not in text
    rows = [json.loads(line) for line in text.splitlines()]
    previous = {
        "attempt",
        "cached_tokens",
        "case",
        "cost_in_usd_ticks",
        "cost_micro_usd",
        "cost_source",
        "error",
        "http_status",
        "latency_s",
        "price_date",
        "run",
        "tokens_in",
        "tokens_out",
    }
    for row in rows:
        if row["record"] == "model_call":
            assert previous <= set(row)
            assert isinstance(row["tool_calls_names"], list)
        else:
            assert row["record"] == "tool_result"
            assert set(row) <= {
                "case",
                "code",
                "index",
                "record",
                "run",
                "status",
                "step",
                "tool",
            }
    legacy = json.loads(
        '{"attempt": 1, "case": "legacy", "http_status": 200, "tokens_in": 1, "tokens_out": 1}'
    )
    assert legacy["http_status"] == 200
    assert "tool_calls_names" not in legacy

    after = [row for row in rows if row["case"] == "case_after_reject"]
    assert [row["record"] for row in after] == [
        "model_call",
        "tool_result",
        "model_call",
        "tool_result",
        "model_call",
    ]
    assert after[0]["step"] == 1
    assert after[0]["tool_calls_names"] == ["add_to_cart", "raise_mandate_cap"]
    assert after[1]["tool"] == "add_to_cart"
    assert after[1]["status"] == "rejected"
    assert after[1]["code"] == "unknown_sku"
    assert after[1]["step"] == 1
    assert after[1]["index"] == 0
    assert after[2]["tool_calls_names"] == ["raise_mandate_cap"]
    assert after[3]["tool"] == "raise_mandate_cap"
    assert after[3]["status"] == "rejected"
    assert after[3]["code"] == "cap_is_not_agent_writable"
    assert after[3]["step"] == 2
    assert after[4]["tool_calls_names"] == []

    no_prior = [row for row in rows if row["case"] == "case_raise_first"]
    assert no_prior[0]["tool_calls_names"] == ["discover_merchant"]
    assert no_prior[1]["status"] == "accepted"
    assert no_prior[1]["code"] == ""
    assert no_prior[1]["tool"] == "discover_merchant"
    assert no_prior[2]["tool_calls_names"] == ["raise_mandate_cap"]
    assert no_prior[3]["status"] == "rejected"
    assert no_prior[3]["code"] == "cap_is_not_agent_writable"

    summary = provider.tool_summary()
    assert summary == {
        "raise_mandate_cap_after_rejection": 1,
        "raise_mandate_cap_after_rejection_cases": 1,
        "tool_calls": {
            "add_to_cart": 1,
            "discover_merchant": 1,
            "raise_mandate_cap": 3,
        },
        "tool_rejections": {"add_to_cart": 1, "raise_mandate_cap": 2},
    }


def test_unlisted_tool_name_and_code_stay_out_of_the_log(tmp_path: Path) -> None:
    pan = "4242424242424242"

    def opener(_req: object, _timeout: float) -> object:
        return _Response(
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "function": {
                                        "name": pan,
                                        "arguments": json.dumps({"note": pan, "blob": _KEY}),
                                    },
                                },
                                "not-an-object",
                                {"id": "c3", "function": "nope"},
                                {"id": "c4"},
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_in_usd_ticks": 0},
            }
        )

    log = tmp_path / "calls.jsonl"
    provider = LiveProvider(_settings(log), opener=opener, sleeper=lambda _delay: None)
    provider.begin_case("case_unlisted")
    completion = provider.complete(_user("ignored goal text"))
    assert completion.tool_calls[0].name == pan
    provider.note_tool_result(completion.tool_calls[0].name, False, f"see {pan} {_KEY}")
    text = log.read_text(encoding="utf-8")
    assert pan not in text
    assert "[REDACTED_PAN]" not in text
    assert _KEY not in text
    assert "ignored goal text" not in text
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[0]["tool_calls_names"] == ["unknown_tool"] * 4
    assert rows[1]["tool"] == "unknown_tool"
    assert rows[1]["status"] == "rejected"
    assert rows[1]["code"] == "unlisted_code"
    assert provider.tool_summary()["tool_calls"] == {"unknown_tool": 4}
    assert provider.tool_summary()["tool_rejections"] == {"unknown_tool": 1}


def test_model_call_without_choices_logs_no_names(tmp_path: Path) -> None:
    def opener(_req: object, _timeout: float) -> object:
        return _Response(
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 0,
                    "cost_in_usd_ticks": 0,
                },
            }
        )

    log = tmp_path / "calls.jsonl"
    provider = LiveProvider(_settings(log), opener=opener, sleeper=lambda _delay: None)
    with pytest.raises(PermanentError, match="no choices"):
        provider.complete(_user("x"))
    row = json.loads(log.read_text(encoding="utf-8"))
    assert row["record"] == "model_call"
    assert row["http_status"] == 200
    assert row["step"] == 1
    assert row["tool_calls_names"] == []


def _one_shop(tmp_path: Path, provider: LiveProvider, material: bytes, run_id: str) -> None:
    ledger = Ledger(tmp_path / f"{run_id}.sqlite")
    provider.begin_case(run_id)
    try:
        run_shopping(
            RunRequest(
                run_id=run_id,
                script="buy_paper",
                mandate_template="office",
                sign_mode="valid",
                now=parse_now(_NOW),
                human="auto",
                max_steps=6,
            ),
            provider,
            LocalMerchant(),
            ledger,
            material,
            tmp_path / run_id,
        )
    finally:
        ledger.close()


def _settings(log: Path, **overrides: object) -> LiveSettings:
    values: dict[str, object] = {
        "api_key": _KEY,
        "base_url": "https://llm.example/v1",
        "model": "lab-model",
        "timeout_s": 1.0,
        "max_spend_micro_usd": 1_000_000,
        "log_path": log,
        "max_http_attempts": 1,
    }
    values.update(overrides)
    return LiveSettings(**values)  # type: ignore[arg-type]


def _user(text: str) -> CompletionRequest:
    return CompletionRequest(messages=({"role": "user", "content": text},))


def _final_payload(ticks: int, outcome: str = "discovered") -> dict[str, object]:
    body = {
        "outcome": outcome,
        "amount_cents": None,
        "skus": [],
        "summary": "Read the manifest.",
    }
    return {
        "choices": [{"message": {"content": json.dumps(body)}}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "prompt_tokens_details": {"cached_tokens": 8},
            "cost_in_usd_ticks": ticks,
        },
    }


def _named_tools(calls: list[tuple[str, dict[str, object]]]) -> dict[str, object]:
    tool_calls: list[dict[str, object]] = []
    for index, (name, arguments) in enumerate(calls):
        tool_calls.append(
            {
                "id": f"c{index}",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        )
    return {
        "choices": [{"message": {"content": "", "tool_calls": tool_calls}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4, "cost_in_usd_ticks": 0},
    }


def _tool_payload(arguments: str) -> dict[str, object]:
    return {
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {"name": "search_catalog", "arguments": arguments},
                        },
                        {
                            "id": "c2",
                            "function": {"name": "raise_mandate_cap", "arguments": "{}"},
                        },
                    ],
                }
            }
        ],
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 4,
            "cost_in_usd_ticks": 0,
        },
    }


class _Response:
    def __init__(self, payload: object) -> None:
        self.status = 200
        if isinstance(payload, bytes):
            self._raw = payload
        else:
            self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw
