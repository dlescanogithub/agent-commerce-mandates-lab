# 0008. Opt-in live tool calling

## Status

Accepted.

## Context

The cassette suite proves the controls against a stub planner. It does not show what a hosted model does when it can call the same tools. A measured pass on 2026-10-18 needed tool schemas. The provider at measurement time did not send them, so that sample used a scratch adapter outside the repo. That commit hash no longer exists. Snapshot commit `36daf60` includes the later provider, which does send schemas; the sample was not measured on that tree.

## Decision

`make eval-live` is the only command that sends. It requires `LIVE_ENABLED=1`. The key is `XAI_API_KEY` and is not written to the call log, the cassette files, or the report. The base URL and the model are configurable. The default model is `grok-4.20-0309-non-reasoning` and the default base URL is `https://api.x.ai/v1`.

The request carries the eight tools the repo actually implements, including `raise_mandate_cap`. That tool is a probe. `tools.execute` always returns `cap_is_not_agent_writable`. The signed cap does not move.

Before each request the adapter checks `MAX_LIVE_SPEND_USD`. Cost is `usage.cost_in_usd_ticks` when the response includes it (10^10 ticks per USD). If the field is absent, the operator must set `LIVE_INPUT_USD_PER_MILLION`, `LIVE_OUTPUT_USD_PER_MILLION`, and `LIVE_PRICE_DATE` together. Otherwise the next request is not sent. HTTP retries stop at `LIVE_HTTP_ATTEMPTS` (1 to 3, default 2) and use the same backoff cap as payments. The call log is JSONL: status, latency, tokens in, out, and cached, cost, and the case id, plus the tool names on that response. An executed tool is a second line (`accepted` or `rejected`, and the rejection code), tied to the call by a step id. Not the prompt, not arguments, and not the result body. The field list is in METRICS.

`eval live` still does not send. CI runs it neither with `LIVE_ENABLED` nor with a key, and the workflow fails if `eval-live` exits 0. Pytest uses a fake opener.

The 2026-10-18 numbers in the README are that scratch sample, copied into `docs/live/`. This decision does not turn them into a score for a later prompt.

## Consequences

A person with a key can spend. The cap is a process limit, not a vendor account limit. A partial pass is a partial pass and has to be described that way. The runner, the tools, the mandate, the ledger, and the ten checks stay the controls. The model does not.
