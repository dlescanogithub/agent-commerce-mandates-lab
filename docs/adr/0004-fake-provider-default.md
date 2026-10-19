# 0004. The stub planner is the default

## Status

Accepted.

## Context

A lab that calls a hosted model in CI spends money and goes red when the model changes, which is a different question from whether the controls hold.

## Decision

`LLM_PROVIDER` defaults to `fake`. The stub follows a named script. Some scripts do the wrong thing on purpose so the tools can refuse them. Cassettes freeze those turns. `python -m agent_commerce.evalkit live` does not send. A hosted pass is a different command, `eval-live`, and it sends only when `LIVE_ENABLED=1`. CI does not set that. Two xAI records from 2026-10-18 are in `docs/live/`: the earlier scratch-adapter sample (`REPORT.md`) and the native one-pass measurement (`native_v2/`). Neither is the CI gate. See ADR 0008.

## Consequences

Changing the stub script changes the cassettes, and the unit test that re-records in memory will fail until the files are updated on purpose. CI never needs a network call to a model vendor.
