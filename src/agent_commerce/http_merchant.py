"""Stdlib HTTP wrapper around the local merchant. Loopback only.

The eval suite does not use this. The demo does, so the discovery manifest
is fetched over HTTP on 127.0.0.1. There is no public bind.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol, runtime_checkable
from urllib import error, request

from agent_commerce.merchant import LocalMerchant


@runtime_checkable
class MerchantPort(Protocol):
    def discovery(self) -> dict[str, object]: ...

    def search_catalog(self, merchant_id: str, query: str) -> dict[str, object]: ...

    def add_to_cart(self, sku: str, qty: int) -> dict[str, object]: ...

    def checkout(self) -> dict[str, object]: ...

    def pay(self, checkout_id: str, idempotency_key: str) -> dict[str, object]: ...

    def refund(self, charge_id: str) -> dict[str, object]: ...

    def order(self, order_id: str) -> dict[str, object]: ...


def dispatch(
    merchant: LocalMerchant, method: str, path: str, body: dict[str, object] | None
) -> tuple[int, dict[str, object]]:
    payload = body or {}
    route = path.split("?", 1)[0]
    if method == "GET" and route == "/.well-known/ucp":
        return 200, merchant.discovery()
    if method == "GET" and route == "/health":
        return 200, {"ok": True, "lab": True}
    if method == "POST" and route == "/catalog":
        merchant_id = _str_field(payload, "merchant_id")
        query = payload.get("query")
        return 200, merchant.search_catalog(merchant_id, query if isinstance(query, str) else "")
    if method == "POST" and route == "/cart":
        sku = _str_field(payload, "sku")
        qty = payload.get("qty")
        if isinstance(qty, bool) or not isinstance(qty, int):
            return 400, {"ok": False, "error": "bad_qty"}
        return 200, merchant.add_to_cart(sku, qty)
    if method == "POST" and route == "/checkout":
        return 200, merchant.checkout()
    if method == "POST" and route == "/pay":
        checkout_id = _str_field(payload, "checkout_id")
        key = _str_field(payload, "idempotency_key")
        try:
            return 200, merchant.pay(checkout_id, key)
        except TimeoutError:
            return 504, {"ok": False, "status": 504, "error": "simulated_timeout"}
    if method == "POST" and route == "/refunds":
        return 200, merchant.refund(_str_field(payload, "charge_id"))
    if method == "GET" and route.startswith("/orders/"):
        return 200, merchant.order(route.removeprefix("/orders/"))
    return 404, {"ok": False, "error": "not_found"}


def _str_field(payload: dict[str, object], name: str) -> str:
    value = payload.get(name)
    return value if isinstance(value, str) else ""


def _build_handler(merchant: LocalMerchant) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def do_GET(self) -> None:
            status, body = dispatch(merchant, "GET", self.path, None)
            _send(self, status, body)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                _send(self, 400, {"ok": False, "error": "bad_json"})
                return
            if not isinstance(parsed, dict):
                _send(self, 400, {"ok": False, "error": "bad_json"})
                return
            body = {str(key): value for key, value in parsed.items()}
            status, response = dispatch(merchant, "POST", self.path, body)
            _send(self, status, response)

    return Handler


def _send(handler: BaseHTTPRequestHandler, status: int, body: dict[str, object]) -> None:
    encoded = json.dumps(body, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def serve(merchant: LocalMerchant, host: str, port: int) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("merchant HTTP server refuses a non-loopback host")
    return ThreadingHTTPServer((host, port), _build_handler(merchant))


class HttpMerchantClient:
    """MerchantPort that talks to the loopback stub. Used by the demo."""

    def __init__(self, base_url: str, timeout_s: float = 5.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    def discovery(self) -> dict[str, object]:
        return self._call("GET", "/.well-known/ucp", None)

    def search_catalog(self, merchant_id: str, query: str) -> dict[str, object]:
        return self._call("POST", "/catalog", {"merchant_id": merchant_id, "query": query})

    def add_to_cart(self, sku: str, qty: int) -> dict[str, object]:
        return self._call("POST", "/cart", {"sku": sku, "qty": qty})

    def checkout(self) -> dict[str, object]:
        return self._call("POST", "/checkout", {})

    def pay(self, checkout_id: str, idempotency_key: str) -> dict[str, object]:
        try:
            return self._call(
                "POST",
                "/pay",
                {"checkout_id": checkout_id, "idempotency_key": idempotency_key},
            )
        except error.HTTPError as exc:
            if exc.code == 504:
                raise TimeoutError("simulated_timeout") from exc
            raise

    def refund(self, charge_id: str) -> dict[str, object]:
        return self._call("POST", "/refunds", {"charge_id": charge_id})

    def order(self, order_id: str) -> dict[str, object]:
        return self._call("GET", f"/orders/{order_id}", None)

    def _call(self, method: str, path: str, body: dict[str, object] | None) -> dict[str, object]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = request.Request(
            self._base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=self._timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("merchant response was not an object")
        return {str(key): value for key, value in parsed.items()}
