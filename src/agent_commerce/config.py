"""Process configuration. Secrets have no default. The stub planner is the default."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from agent_commerce.errors import ConfigError

ProviderName = Literal["fake", "openai"]

DEFAULT_LIVE_BASE_URL = "https://api.x.ai/v1"
DEFAULT_LIVE_MODEL = "grok-4.20-0309-non-reasoning"


@dataclass(frozen=True)
class LiveSettings:
    """Operator-supplied endpoint. The key is never part of ``repr``."""

    api_key: str
    base_url: str
    model: str
    timeout_s: float
    max_spend_micro_usd: int
    log_path: Path | None = None
    max_http_attempts: int = 2
    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None
    price_date: str = ""
    run_label: str = "live"

    def __repr__(self) -> str:
        return (
            "LiveSettings(api_key='[REDACTED]', "
            f"base_url={self.base_url!r}, model={self.model!r}, "
            f"timeout_s={self.timeout_s!r}, "
            f"max_spend_micro_usd={self.max_spend_micro_usd!r})"
        )


@dataclass(frozen=True)
class Config:
    llm_provider: ProviderName
    live: LiveSettings | None
    database_path: Path
    trace_dir: Path
    evals_dir: Path
    lab_key_dir: Path | None
    check_threshold: float
    max_payment_attempts: int
    max_agent_steps: int
    log_level: str
    merchant_host: str
    merchant_port: int

    @staticmethod
    def from_env(environ: dict[str, str] | None = None) -> Config:
        env: Mapping[str, str] = os.environ if environ is None else environ
        provider = _provider_name(env.get("LLM_PROVIDER", "fake"))
        key_dir = env.get("LAB_KEY_DIR", "").strip()
        return Config(
            llm_provider=provider,
            live=_live_settings(env, provider),
            database_path=Path(env.get("DATABASE_PATH", "var/runtime.sqlite")),
            trace_dir=Path(env.get("TRACE_DIR", "var/traces")),
            evals_dir=Path(env.get("EVALS_DIR", "evals")),
            lab_key_dir=Path(key_dir) if key_dir else None,
            check_threshold=_float(env.get("EVAL_CHECK_THRESHOLD", "1.0"), "EVAL_CHECK_THRESHOLD"),
            max_payment_attempts=_int(env.get("MAX_PAYMENT_ATTEMPTS", "3"), "MAX_PAYMENT_ATTEMPTS"),
            max_agent_steps=_int(env.get("MAX_AGENT_STEPS", "12"), "MAX_AGENT_STEPS"),
            log_level=env.get("LOG_LEVEL", "INFO"),
            merchant_host=_loopback(env.get("MERCHANT_HOST", "127.0.0.1")),
            merchant_port=_int(env.get("MERCHANT_PORT", "8765"), "MERCHANT_PORT"),
        )


def _provider_name(raw: str) -> ProviderName:
    if raw == "fake":
        return "fake"
    if raw == "openai":
        return "openai"
    raise ConfigError("LLM_PROVIDER must be fake or openai")


def _live_settings(env: Mapping[str, str], provider: ProviderName) -> LiveSettings | None:
    live = env.get("LIVE_MODE", "").strip() == "1"
    if provider == "fake":
        if live:
            raise ConfigError(
                "LIVE_MODE=1 cannot be combined with LLM_PROVIDER=fake. "
                "The stub does not call a hosted model."
            )
        return None
    if not live:
        raise ConfigError(
            "A hosted provider requires LIVE_MODE=1. Live mode is off by default "
            "and CI does not set it. No request was sent."
        )
    missing = [
        name
        for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "MAX_LIVE_SPEND_USD")
        if not env.get(name, "").strip()
    ]
    if missing:
        raise ConfigError("LIVE_MODE=1 is missing " + ", ".join(missing) + ". No request was sent.")
    base = env["LLM_BASE_URL"].strip()
    parsed = urlparse(base)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise ConfigError("LLM_BASE_URL must be an http or https URL. No request was sent.")
    spend = _float(env["MAX_LIVE_SPEND_USD"], "MAX_LIVE_SPEND_USD")
    if spend <= 0:
        raise ConfigError("MAX_LIVE_SPEND_USD must be positive. No request was sent.")
    timeout = _float(env.get("LLM_TIMEOUT_S", "30"), "LLM_TIMEOUT_S")
    return LiveSettings(
        api_key=env["LLM_API_KEY"].strip(),
        base_url=base.rstrip("/"),
        model=env["LLM_MODEL"].strip(),
        timeout_s=timeout,
        max_spend_micro_usd=int(spend * 1_000_000),
    )


def load_live_eval(env: Mapping[str, str] | None = None) -> LiveSettings:
    """Settings for ``make eval-live``. Refuses to build them unless LIVE_ENABLED=1.

    The key is read only from ``XAI_API_KEY``. This function does not open a socket.
    """

    source: Mapping[str, str] = os.environ if env is None else env
    if source.get("LIVE_ENABLED", "").strip() != "1":
        raise ConfigError("LIVE_ENABLED must be 1. No request was sent.")
    key = source.get("XAI_API_KEY", "").strip()
    if not key:
        raise ConfigError("XAI_API_KEY is missing. No request was sent.")
    spend_raw = source.get("MAX_LIVE_SPEND_USD", "").strip()
    if not spend_raw:
        raise ConfigError("MAX_LIVE_SPEND_USD is missing. No request was sent.")
    spend = _float(spend_raw, "MAX_LIVE_SPEND_USD")
    if spend <= 0:
        raise ConfigError("MAX_LIVE_SPEND_USD must be positive. No request was sent.")
    base = source.get("XAI_BASE_URL", "").strip() or DEFAULT_LIVE_BASE_URL
    parsed = urlparse(base)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise ConfigError("XAI_BASE_URL must be an http or https URL. No request was sent.")
    model = source.get("XAI_MODEL", "").strip() or DEFAULT_LIVE_MODEL
    timeout = _float(source.get("XAI_TIMEOUT_S", "60"), "XAI_TIMEOUT_S")
    if timeout <= 0:
        raise ConfigError("XAI_TIMEOUT_S must be positive. No request was sent.")
    attempts = _int(source.get("LIVE_HTTP_ATTEMPTS", "2"), "LIVE_HTTP_ATTEMPTS")
    if attempts < 1 or attempts > 3:
        raise ConfigError("LIVE_HTTP_ATTEMPTS must be from 1 to 3. No request was sent.")
    log_raw = source.get("LIVE_LOG_PATH", "").strip() or "var/live/calls.jsonl"
    input_price, output_price, price_date = _live_prices(source)
    micro = int((Decimal(str(spend)) * Decimal(1_000_000)).to_integral_value())
    return LiveSettings(
        api_key=key,
        base_url=base.rstrip("/"),
        model=model,
        timeout_s=timeout,
        max_spend_micro_usd=micro,
        log_path=Path(log_raw),
        max_http_attempts=attempts,
        input_usd_per_million=input_price,
        output_usd_per_million=output_price,
        price_date=price_date,
        run_label=source.get("LIVE_RUN_LABEL", "").strip() or "live",
    )


def _live_prices(env: Mapping[str, str]) -> tuple[float | None, float | None, str]:
    raw_in = env.get("LIVE_INPUT_USD_PER_MILLION", "").strip()
    raw_out = env.get("LIVE_OUTPUT_USD_PER_MILLION", "").strip()
    price_date = env.get("LIVE_PRICE_DATE", "").strip()
    if not raw_in and not raw_out and not price_date:
        return None, None, ""
    if not raw_in or not raw_out or not price_date:
        raise ConfigError(
            "LIVE_INPUT_USD_PER_MILLION, LIVE_OUTPUT_USD_PER_MILLION, and "
            "LIVE_PRICE_DATE must be set together. No request was sent."
        )
    try:
        input_price = float(raw_in)
        output_price = float(raw_out)
    except ValueError as exc:
        raise ConfigError("live token prices must be numbers. No request was sent.") from exc
    if input_price < 0 or output_price < 0:
        raise ConfigError("live token prices must be >= 0. No request was sent.")
    return input_price, output_price, price_date


def _loopback(raw: str) -> str:
    host = raw.strip()
    if host not in ("127.0.0.1", "localhost"):
        raise ConfigError("MERCHANT_HOST must be 127.0.0.1 or localhost")
    return host


def _int(raw: str, label: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{label} must be an integer") from exc
    if value < 0:
        raise ConfigError(f"{label} must be >= 0")
    return value


def _float(raw: str, label: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{label} must be a number") from exc
    return value
