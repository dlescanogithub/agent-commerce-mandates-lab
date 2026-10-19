# 0005. Idempotency, bounded retries, dead letter

## Status

Accepted.

## Context

A payment call can time out after the rail has captured, or it can return an error and be safe to retry. Retrying without a stable key double-charges. Retrying forever stalls the process.

## Decision

The tool derives one idempotency key per mandate and checkout. The merchant rail and the SQLite ledger both treat that key as unique. A second call returns the original charge. Timeouts and HTTP 500s retry up to `MAX_PAYMENT_ATTEMPTS` (default 3). The delay is exponential with jitter and capped at 8 seconds (`src/agent_commerce/backoff.py`). The eval harness records the delay and does not sleep. After the last retry, the attempt is inserted into `dead_letters` and no charge row is written. A policy refusal (cap, category, currency, human) is not retried.

A `duplicate` fault returns two delivery counts and one capture.

## Consequences

The cap is tested in `tests/test_mandate_and_money.py`. The suite does not wait 8 seconds. A reviewer who wants to see a real sleep can call `retry_delay_s` and sleep that value outside CI.
