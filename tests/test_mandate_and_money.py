from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent_commerce.backoff import CAP_S, retry_delay_s
from agent_commerce.catalog import INJECTION_SENTENCE, by_sku, search
from agent_commerce.keys import generate_lab_key
from agent_commerce.ledger import Charge, Ledger
from agent_commerce.mandate import (
    office_template,
    prepare_mandate,
    sign_mandate,
    verify_mandate,
)
from agent_commerce.merchant import LocalMerchant
from agent_commerce.pricing import cost_micro_usd

NOW = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)


def test_valid_office_mandate_verifies() -> None:
    key = generate_lab_key()
    try:
        mandate = prepare_mandate("office", "valid", key.material, NOW)
        assert mandate.valid
        assert mandate.cap_cents == 20000
        assert mandate.reason == "ok"
    finally:
        key.close()


def test_signature_failures_are_closed() -> None:
    key = generate_lab_key()
    try:
        for mode in ("tamper_sig", "tamper_body", "foreign", "unsigned", "expired"):
            mandate = prepare_mandate("office", mode, key.material, NOW)
            assert not mandate.valid
            assert mandate.cap_cents == 0
    finally:
        key.close()


def test_malformed_and_limit_failures() -> None:
    key = b"k" * 32
    body = office_template()
    broken = dict(body)
    broken["expires_at"] = "not-a-time"
    assert verify_mandate(broken, sign_mandate(broken, key), key, NOW).reason == "malformed"
    wrong_currency = dict(body)
    wrong_currency["currency"] = "USD"
    signed = sign_mandate(wrong_currency, key)
    assert verify_mandate(wrong_currency, signed, key, NOW).reason == "currency"
    tiny = dict(body)
    tiny["cap_cents"] = 0
    assert verify_mandate(tiny, sign_mandate(tiny, key), key, NOW).reason == "limits"
    empty = dict(body)
    empty["allowed_merchants"] = []
    assert verify_mandate(empty, sign_mandate(empty, key), key, NOW).reason == "allow_list"
    missing = dict(body)
    del missing["nonce"]
    assert verify_mandate(missing, "abcd", key, NOW).reason in {"malformed", "bad_signature"}


def test_unknown_template_and_mode() -> None:
    with pytest.raises(ValueError):
        prepare_mandate("travel", "valid", b"k" * 32, NOW)
    with pytest.raises(ValueError):
        prepare_mandate("office", "nope", b"k" * 32, NOW)


def test_catalog_search_and_injection_is_data() -> None:
    assert by_sku("NOPE") is None
    paper = search("mercado-ficticio", "paper")
    assert [item.sku for item in paper] == ["PAPER-A4"]
    gift = by_sku("GIFT-CARD")
    assert gift is not None
    assert INJECTION_SENTENCE in gift.description
    assert search("bazar-inventado", "")[0].sku == "MUG-01"


def test_merchant_price_change_faults_and_refund() -> None:
    merchant = LocalMerchant(faults=["duplicate"], price_override_cents=2100)
    assert merchant.discovery()["lab"] is True
    assert merchant.search_catalog("nope", "x")["error"] == "unknown_merchant"
    assert merchant.add_to_cart("NOPE", 1)["error"] == "unknown_sku"
    assert merchant.add_to_cart("PAPER-A4", 0)["error"] == "bad_qty"
    merchant.add_to_cart("PAPER-A4", 2)
    first = merchant.checkout()
    assert first["error"] == "price_changed"
    assert first["total_cents"] == 4200
    second = merchant.checkout()
    assert second["ok"] is True
    again = merchant.checkout()
    assert again["checkout_id"] == second["checkout_id"]
    paid = merchant.pay(str(second["checkout_id"]), "key-1")
    assert paid["deliveries"] == 2
    replay = merchant.pay(str(second["checkout_id"]), "key-1")
    assert replay["replayed"] is True
    assert merchant.add_to_cart("PEN-BLUE", 1)["error"] == "cart_closed"
    assert merchant.checkout()["error"] == "already_paid"
    assert merchant.pay("missing", "other")["error"] == "unknown_checkout"
    refunded = merchant.refund(str(paid["charge_id"]))
    assert refunded["status"] == "refunded"
    assert merchant.refund("missing")["error"] == "unknown_charge"
    assert merchant.order("missing")["error"] == "not_found"


def test_unknown_fault_and_timeout() -> None:
    merchant = LocalMerchant(faults=["nope"])
    merchant.add_to_cart("PEN-BLUE", 1)
    order = merchant.checkout()
    assert merchant.pay(str(order["checkout_id"]), "k")["error"] == "unknown_fault:nope"
    timing = LocalMerchant(faults=["timeout"])
    timing.add_to_cart("PEN-BLUE", 1)
    opened = timing.checkout()
    with pytest.raises(TimeoutError):
        timing.pay(str(opened["checkout_id"]), "k")


def test_ledger_idempotency_and_dead_letter(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.sqlite")
    charge = Charge(
        charge_id="chg-1",
        idempotency_key="mnd:chk-1",
        mandate_id="mnd_office",
        checkout_id="chk-1",
        merchant_id="mercado-ficticio",
        amount_cents=3600,
        currency="LAB",
        skus=("PAPER-A4",),
        categories=("office_supplies",),
        max_unit_cents=1800,
        approval_id=None,
    )
    assert ledger.insert_charge(charge).charge_id == "chg-1"
    assert ledger.insert_charge(charge).charge_id == "chg-1"
    assert ledger.charge_count("mnd_office") == 1
    assert ledger.spent_cents("mnd_office") == 3600
    assert ledger.insert_refund("chg-1", 3600) is True
    assert ledger.insert_refund("chg-1", 3600) is False
    assert ledger.spent_cents("mnd_office") == 0
    ledger.dead_letter("mnd_office", "chk-2", "simulated_500", 3)
    ledger.dead_letter("mnd_office", "chk-2", "simulated_500", 3)
    assert ledger.dead_count("mnd_office") == 1
    decision = ledger.record_decision("chk-1", "approve")
    assert ledger.approved("chk-1") == decision
    assert ledger.approval_count() == 1
    assert ledger.checkout_charged("chk-1") is True
    assert ledger.get_charge("missing") is None
    assert ledger.latest_charge("missing") is None
    ledger.close()


def test_backoff_is_capped() -> None:
    import random

    rng = random.Random(0)
    assert retry_delay_s(1, 100.0, rng) == CAP_S
    assert 0 < retry_delay_s(1, None, rng) <= CAP_S
    assert retry_delay_s(8, None, rng) <= CAP_S
    assert cost_micro_usd(1_000_000, 0) == 150_000


def test_key_file_mode(tmp_path: Path) -> None:
    key = generate_lab_key(tmp_path)
    assert key.path is not None
    assert key.path.stat().st_mode & 0o777 == 0o600
    assert "NOT REAL" in (tmp_path / "NOT_REAL.txt").read_text(encoding="utf-8")
    assert len(key.material) == 32
