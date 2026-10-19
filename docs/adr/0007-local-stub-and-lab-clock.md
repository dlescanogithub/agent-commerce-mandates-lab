# 0007. Local stub merchant and a pinned lab clock

## Status

Accepted.

## Context

The eval has to mean the same thing next month. A wall clock would eventually expire the sample mandates. A real payment network would make CI flaky and would not be synthetic.

## Decision

The merchant is an in-process object. The demo also serves it with the standard library on `127.0.0.1`. Prices are simulated `LAB` cents. Faults (`timeout`, `http_500`, `duplicate`) and a one-shot price override are the failure simulator.

Golden cases pass `now` as `2026-10-18T15:00:00Z`. Expiry is compared to that instant, not to the clock on the machine. A real integration would use the system clock and a short mandate lifetime. That swap is one function, and it is not what CI runs.

SQLite is the ledger for a single process. It is not Postgres and it has no row locking across workers.

## Consequences

Two demo processes do not share a ledger. A killed process leaves a SQLite file under the work directory the caller chose. The demo directory is `var/demo` unless `--work` is set.
