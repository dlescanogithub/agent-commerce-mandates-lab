"""In-process stub merchant: discovery, catalog, cart, checkout, pay, refund, order.

The payment rail is fake. Idempotency keys return the original capture.
Fault names (`timeout`, `http_500`, `duplicate`) are a failure simulator.
Prices are simulated LAB cents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_commerce.catalog import MERCHANTS, Product, by_sku, search


@dataclass
class Line:
    sku: str
    name: str
    merchant_id: str
    category: str
    qty: int
    unit_cents: int

    @property
    def total_cents(self) -> int:
        return self.qty * self.unit_cents

    def view(self) -> dict[str, object]:
        return {
            "category": self.category,
            "merchant_id": self.merchant_id,
            "name": self.name,
            "qty": self.qty,
            "sku": self.sku,
            "total_cents": self.total_cents,
            "unit_cents": self.unit_cents,
        }


@dataclass
class LocalMerchant:
    """One cart, one open checkout, a fake rail. State is process-local."""

    faults: list[str] = field(default_factory=list)
    price_override_cents: int | None = None
    override_sku: str = "PAPER-A4"
    cart: list[Line] = field(default_factory=list)
    checkout_seq: int = 1
    open_order: dict[str, object] | None = None
    orders: dict[str, dict[str, object]] = field(default_factory=dict)
    payments: dict[str, dict[str, object]] = field(default_factory=dict)
    price_pending: bool = False

    def __post_init__(self) -> None:
        self.faults = list(self.faults)
        if self.price_override_cents is not None:
            self.price_pending = True

    def discovery(self) -> dict[str, object]:
        return {
            "lab": True,
            "not_a_conformant_ucp_profile": True,
            "currency": "LAB",
            "note": (
                "Local discovery manifest for this lab. Inspired by a public "
                "commerce-profile idea. Not a UCP profile and not a live host."
            ),
            "merchants": [
                {
                    "merchant_id": merchant_id,
                    "display_name": name,
                    "endpoints": {
                        "catalog": "/catalog",
                        "cart": "/cart",
                        "checkout": "/checkout",
                        "pay": "/pay",
                        "orders": "/orders",
                        "refunds": "/refunds",
                    },
                }
                for merchant_id, name in MERCHANTS.items()
            ],
        }

    def search_catalog(self, merchant_id: str, query: str) -> dict[str, object]:
        if merchant_id not in MERCHANTS:
            return {"ok": False, "error": "unknown_merchant"}
        products = search(merchant_id, query)
        return {
            "ok": True,
            "merchant_id": merchant_id,
            "products": [_product_view(product) for product in products],
        }

    def add_to_cart(self, sku: str, qty: int) -> dict[str, object]:
        if self.open_order is not None and self.open_order.get("status") == "paid":
            return {"ok": False, "error": "cart_closed"}
        product = by_sku(sku)
        if product is None:
            return {"ok": False, "error": "unknown_sku"}
        if qty < 1 or qty > 99:
            return {"ok": False, "error": "bad_qty"}
        self.cart.append(
            Line(
                sku=product.sku,
                name=product.name,
                merchant_id=product.merchant_id,
                category=product.category,
                qty=qty,
                unit_cents=product.unit_cents,
            )
        )
        return {"ok": True, "cart": self._cart_view(), "total_cents": self._cart_total()}

    def checkout(self) -> dict[str, object]:
        if not self.cart:
            return {"ok": False, "error": "empty_cart"}
        if self.price_pending:
            self._apply_override()
            self.price_pending = False
            return {
                "ok": False,
                "error": "price_changed",
                "cart": self._cart_view(),
                "total_cents": self._cart_total(),
            }
        if self.open_order is not None and self.open_order.get("status") == "paid":
            return {"ok": False, "error": "already_paid", "order_id": self.open_order["order_id"]}
        if self.open_order is not None and self.open_order.get("status") == "open":
            return {"ok": True, **self.open_order}
        checkout_id = f"chk-{self.checkout_seq}"
        self.checkout_seq += 1
        order_id = f"ord-{checkout_id}"
        merchant_ids = sorted({line.merchant_id for line in self.cart})
        order: dict[str, object] = {
            "ok": True,
            "checkout_id": checkout_id,
            "order_id": order_id,
            "status": "open",
            "currency": "LAB",
            "merchant_ids": merchant_ids,
            "lines": [line.view() for line in self.cart],
            "total_cents": self._cart_total(),
        }
        self.open_order = order
        self.orders[order_id] = order
        return dict(order)

    def pay(self, checkout_id: str, idempotency_key: str) -> dict[str, object]:
        prior = self.payments.get(idempotency_key)
        if prior is not None:
            replay = dict(prior)
            replay["replayed"] = True
            return replay
        order = self.open_order
        if order is None or order.get("checkout_id") != checkout_id:
            return {"ok": False, "error": "unknown_checkout"}
        if order.get("status") == "paid":
            return {"ok": False, "error": "already_paid", "order_id": order["order_id"]}
        if self.faults:
            fault = self.faults.pop(0)
            if fault == "timeout":
                raise TimeoutError("simulated_timeout")
            if fault == "http_500":
                return {"ok": False, "status": 500, "error": "simulated_500"}
            if fault == "duplicate":
                captured = self._capture(order, idempotency_key)
                captured["deliveries"] = 2
                return captured
            return {"ok": False, "error": f"unknown_fault:{fault}"}
        return self._capture(order, idempotency_key)

    def refund(self, charge_id: str) -> dict[str, object]:
        for payment in self.payments.values():
            if payment.get("charge_id") == charge_id and payment.get("ok") is True:
                order_id = payment.get("order_id")
                if isinstance(order_id, str) and order_id in self.orders:
                    self.orders[order_id]["status"] = "refunded"
                return {
                    "ok": True,
                    "charge_id": charge_id,
                    "amount_cents": payment.get("amount_cents"),
                    "status": "refunded",
                }
        return {"ok": False, "error": "unknown_charge"}

    def order(self, order_id: str) -> dict[str, object]:
        found = self.orders.get(order_id)
        if found is None:
            return {"ok": False, "error": "not_found"}
        body = dict(found)
        body["ok"] = True
        return body

    def _capture(self, order: dict[str, object], idempotency_key: str) -> dict[str, object]:
        charge_id = f"chg-{order['checkout_id']}"
        order["status"] = "paid"
        body: dict[str, object] = {
            "ok": True,
            "status": 200,
            "charge_id": charge_id,
            "checkout_id": order["checkout_id"],
            "order_id": order["order_id"],
            "amount_cents": order["total_cents"],
            "currency": "LAB",
            "deliveries": 1,
            "replayed": False,
            "idempotency_key": idempotency_key,
        }
        self.payments[idempotency_key] = body
        return dict(body)

    def _apply_override(self) -> None:
        if self.price_override_cents is None:
            return
        for line in self.cart:
            if line.sku == self.override_sku:
                line.unit_cents = self.price_override_cents

    def _cart_total(self) -> int:
        return sum(line.total_cents for line in self.cart)

    def _cart_view(self) -> list[dict[str, object]]:
        return [line.view() for line in self.cart]


def _product_view(product: Product) -> dict[str, object]:
    return {
        "category": product.category,
        "currency": "LAB",
        "description": product.description,
        "merchant_id": product.merchant_id,
        "name": product.name,
        "sku": product.sku,
        "unit_cents": product.unit_cents,
    }
