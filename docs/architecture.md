# Architecture

The model is untrusted. The mandate and the ledger are the controls. The merchant is a local stub.

```mermaid
flowchart LR
  caller["CLI demo"] --> http["Loopback HTTP stub"]
  caller --> runner["Shopping loop"]
  runner --> model["Planner"]
  model --> fake["Fake planner, default"]
  model --> cassette["Cassette replay, CI"]
  model --> live["HTTP adapter, off in CI; samples in docs/live"]
  runner --> tools["Tools"]
  tools --> mandate["HMAC mandate, fail closed"]
  tools --> merchant["Catalog, cart, checkout"]
  tools --> human{"Above the human line?"}
  human -->|yes| person["Simulated approver"]
  person -->|approve| rail["Fake rail, idempotency key"]
  person -->|reject| runner
  human -->|no| rail
  rail --> ledger["SQLite ledger and dead letter"]
  runner --> trace["JSONL trace, redacted"]
```

## Trust boundaries

- The planner may propose any tool, including `raise_mandate_cap` and a card field. The tool layer drops those.
- The amount crosses the boundary as the checkout total, not as a model argument.
- The idempotency key is derived inside the tool.
- Logs and traces do not receive catalog descriptions. They do receive tool arguments, after redaction.
- The HTTP server is loopback. The eval suite does not need it. The demo uses it so the manifest is fetched over HTTP.

## Data

| Store | Holds | Does not hold |
|---|---|---|
| Mandate body | Cap, expiry, allow-lists, threshold, nonce | The HMAC key |
| SQLite ledger | Charges, refunds, decisions, dead letters | Card numbers |
| JSONL trace | Events, token counts, tool name, ok/error | Descriptions, keys |
| Cassette | Frozen planner turns | Tool results. Those are recomputed. |

## Lab clock

Cases pass `2026-10-18T15:00:00Z`. Expiry uses that instant. See ADR 0007.

## What a real deployment would replace

The fake rail, the HMAC key that this process both holds, the simulated approver, and SQLite. The invariant list would stay. That replacement is not started.
