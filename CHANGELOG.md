# Changelog

## Unreleased

- Live call log records the tool names on each model call and, for each executed tool, `accepted` or `rejected` plus the rejection code. Arguments and result bodies are not fields. `summary.json` and the `eval-live` printout add `tool_log`: calls per tool, rejections per tool, and how many `raise_mandate_cap` names came after a prior rejection in the same case. The runner notifies the live provider with the tool name and the final ok/error only, because the model call is logged before the tool runs and the last tool of a case has no following request. The published 2026-10-18 sample predates these fields.
- Opt-in live eval (`make eval-live`, `LIVE_ENABLED=1`) against an OpenAI-compatible chat endpoint. Default model `grok-4.20-0309-non-reasoning`. Key from `XAI_API_KEY` only. Spend cap, per-call JSONL, tool schemas from the repo tools, including `raise_mandate_cap` as a probe the tools always refuse.
- Recorded an xAI sample from 2026-10-18 under `docs/live/`. The measured commit is not in this history (history was squashed into a clean snapshot; the original commit hashes no longer exist). Snapshot commit `36daf60` includes the later live provider, so the sample was not measured on that tree. Two passes of 37 cases, not three full runs. Safety counts were zero. Expectation matches were 27/37 and 28/37.

## 0.1.0 - 2026-10-18

Lab only. Not a release and not a deployment.

- Local stub merchant (discovery manifest, catalog, cart, checkout, order status).
- Fake payment rail with idempotency, a failure simulator, bounded retries, and a dead-letter table.
- HMAC spending mandates (cap, expiry, merchants, categories, per-item max, human threshold). Lab keys, labelled NOT REAL.
- Cassette-driven stub planner and an invariant eval gate, including a forced regression that must fail.
- Optional HTTP adapter for a hosted model. Off by default. The 0.1.0 adapter did not send tool schemas and had no measured hosted run.

[EST] figures in the docs are illustrative. Measured figures name the command and the date.
