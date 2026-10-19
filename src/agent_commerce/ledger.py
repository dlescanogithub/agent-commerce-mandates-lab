"""Spend ledger for one mandate. SQLite, local file, integer cents.

The running total is captured charges minus refunds. A repeated idempotency
key does not insert a second charge. Failed payments land in the dead-letter
table and do not add to the total.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from agent_commerce.jsonutil import dumps, loads


@dataclass(frozen=True)
class Charge:
    charge_id: str
    idempotency_key: str
    mandate_id: str
    checkout_id: str
    merchant_id: str
    amount_cents: int
    currency: str
    skus: tuple[str, ...]
    categories: tuple[str, ...]
    max_unit_cents: int
    approval_id: str | None


class Ledger:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS charges (
                charge_id TEXT PRIMARY KEY,
                idempotency_key TEXT UNIQUE,
                mandate_id TEXT NOT NULL,
                checkout_id TEXT NOT NULL,
                merchant_id TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                currency TEXT NOT NULL,
                skus_json TEXT NOT NULL,
                categories_json TEXT NOT NULL,
                max_unit_cents INTEGER NOT NULL,
                approval_id TEXT
            );
            CREATE TABLE IF NOT EXISTS refunds (
                refund_id TEXT PRIMARY KEY,
                charge_id TEXT UNIQUE,
                amount_cents INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS dead_letters (
                dead_id TEXT PRIMARY KEY,
                mandate_id TEXT NOT NULL,
                checkout_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                attempts INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                checkout_id TEXT NOT NULL,
                decision TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def spent_cents(self, mandate_id: str) -> int:
        charged = self._conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM charges WHERE mandate_id = ?",
            (mandate_id,),
        ).fetchone()
        refunded = self._conn.execute(
            """
            SELECT COALESCE(SUM(refunds.amount_cents), 0)
            FROM refunds
            JOIN charges ON charges.charge_id = refunds.charge_id
            WHERE charges.mandate_id = ?
            """,
            (mandate_id,),
        ).fetchone()
        charged_cents = int(charged[0]) if charged is not None else 0
        refunded_cents = int(refunded[0]) if refunded is not None else 0
        return charged_cents - refunded_cents

    def charge_count(self, mandate_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM charges WHERE mandate_id = ?",
            (mandate_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def refund_count(self, mandate_id: str) -> int:
        row = self._conn.execute(
            """
            SELECT COUNT(*) FROM refunds
            JOIN charges ON charges.charge_id = refunds.charge_id
            WHERE charges.mandate_id = ?
            """,
            (mandate_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def dead_count(self, mandate_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM dead_letters WHERE mandate_id = ?",
            (mandate_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def approval_count(self, decision: str = "approve") -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE decision = ?",
            (decision,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def get_charge(self, idempotency_key: str) -> Charge | None:
        row = self._conn.execute(
            """
            SELECT charge_id, idempotency_key, mandate_id, checkout_id, merchant_id,
                   amount_cents, currency, skus_json, categories_json, max_unit_cents, approval_id
            FROM charges WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        return _charge_from_row(row)

    def latest_charge(self, mandate_id: str) -> Charge | None:
        row = self._conn.execute(
            """
            SELECT charge_id, idempotency_key, mandate_id, checkout_id, merchant_id,
                   amount_cents, currency, skus_json, categories_json, max_unit_cents, approval_id
            FROM charges WHERE mandate_id = ?
            ORDER BY rowid DESC LIMIT 1
            """,
            (mandate_id,),
        ).fetchone()
        if row is None:
            return None
        return _charge_from_row(row)

    def charges(self, mandate_id: str) -> list[Charge]:
        rows = self._conn.execute(
            """
            SELECT charge_id, idempotency_key, mandate_id, checkout_id, merchant_id,
                   amount_cents, currency, skus_json, categories_json, max_unit_cents, approval_id
            FROM charges WHERE mandate_id = ? ORDER BY rowid
            """,
            (mandate_id,),
        ).fetchall()
        return [_charge_from_row(row) for row in rows]

    def insert_charge(self, charge: Charge) -> Charge:
        existing = self.get_charge(charge.idempotency_key)
        if existing is not None:
            return existing
        self._conn.execute(
            """
            INSERT INTO charges (
                charge_id, idempotency_key, mandate_id, checkout_id, merchant_id,
                amount_cents, currency, skus_json, categories_json, max_unit_cents, approval_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                charge.charge_id,
                charge.idempotency_key,
                charge.mandate_id,
                charge.checkout_id,
                charge.merchant_id,
                charge.amount_cents,
                charge.currency,
                dumps(list(charge.skus)),
                dumps(list(charge.categories)),
                charge.max_unit_cents,
                charge.approval_id,
            ),
        )
        self._conn.commit()
        return charge

    def insert_refund(self, charge_id: str, amount_cents: int) -> bool:
        refund_id = f"ref-{charge_id}"
        try:
            self._conn.execute(
                "INSERT INTO refunds (refund_id, charge_id, amount_cents) VALUES (?, ?, ?)",
                (refund_id, charge_id, amount_cents),
            )
        except sqlite3.IntegrityError:
            return False
        self._conn.commit()
        return True

    def dead_letter(self, mandate_id: str, checkout_id: str, reason: str, attempts: int) -> None:
        dead_id = f"dlq-{checkout_id}-{attempts}"
        self._conn.execute(
            """
            INSERT OR IGNORE INTO dead_letters (dead_id, mandate_id, checkout_id, reason, attempts)
            VALUES (?, ?, ?, ?, ?)
            """,
            (dead_id, mandate_id, checkout_id, reason, attempts),
        )
        self._conn.commit()

    def record_decision(self, checkout_id: str, decision: str) -> str:
        decision_id = f"apr-{checkout_id}-{decision}"
        self._conn.execute(
            "INSERT OR IGNORE INTO decisions (decision_id, checkout_id, decision) VALUES (?, ?, ?)",
            (decision_id, checkout_id, decision),
        )
        self._conn.commit()
        return decision_id

    def approved(self, checkout_id: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT decision_id FROM decisions
            WHERE checkout_id = ? AND decision = 'approve'
            """,
            (checkout_id,),
        ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def checkout_charged(self, checkout_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM charges WHERE checkout_id = ?",
            (checkout_id,),
        ).fetchone()
        return row is not None


def _charge_from_row(row: tuple[object, ...]) -> Charge:
    skus_raw = loads(str(row[7]))
    categories_raw = loads(str(row[8]))
    skus = tuple(str(item) for item in skus_raw) if isinstance(skus_raw, list) else ()
    categories = (
        tuple(str(item) for item in categories_raw) if isinstance(categories_raw, list) else ()
    )
    approval = row[10]
    return Charge(
        charge_id=str(row[0]),
        idempotency_key=str(row[1]),
        mandate_id=str(row[2]),
        checkout_id=str(row[3]),
        merchant_id=str(row[4]),
        amount_cents=int(str(row[5])),
        currency=str(row[6]),
        skus=skus,
        categories=categories,
        max_unit_cents=int(str(row[9])),
        approval_id=None if approval is None else str(approval),
    )
