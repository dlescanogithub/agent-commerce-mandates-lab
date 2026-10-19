# Cost

The stub price is synthetic so a run has a number the report can add. It is not a vendor price. Input 150_000 micro-USD per 1,000,000 tokens. Output 600_000 micro-USD per 1,000,000 tokens. That is 0.15 USD and 0.60 USD per million tokens, invented for the lab on 2026-10-18. Source: `src/agent_commerce/pricing.py` in this repo. Not a pricing page.

`LAB` cents are simulated catalog fixtures. They are not a conversion to any currency.

Latency of the stub is in-process. It is not quoted. There is no p50 or p95 to publish for a local function call.

| Scenario | Model / provider | Tokens or units | Cost / run | p50 / p95 latency | Quality | Price date / source |
|---|---|---|---|---|---|---|
| Golden suite, 38 cases | `stub-llm-v1` / cassette replay of the fake planner | 56984 in, 2952 out | 10302 micro-USD | not measured (in-process) | 38/38, checker mean 1.00 | 2026-10-18, synthetic rate in `pricing.py`. Command: `.venv/bin/python -m agent_commerce.evalkit run`. Version 0.1.0. |
| One demo purchase, two reams, empty work directory | same stub | 1509 in, 79 out | 273 micro-USD | not measured (in-process) | 1 charge, 3600 simulated LAB cents, under the human line | 2026-10-18. Command: `.venv/bin/python -m agent_commerce.cli demo --work /tmp/mandate-demo`. A second run on the same directory replays the ledger row and measured 1505 in, 79 out, still 273 micro-USD and 1 charge. |
| Forced regression, 1 case | hand-written cassette | 40 in, 30 out | 24 micro-USD | not measured | 0/1, by design | 2026-10-18. Command: `.venv/bin/python -m agent_commerce.evalkit regression`. |
| xAI sample, two partial passes plus smoke | `grok-4.20-0309-non-reasoning` | 574 calls, 652k tokens in (530k cached), 10k out | US$0.2842 | p50 0.55 s, p95 1.36 s, max 10.6 s | 27/37 and 28/37 against repo expectations. Not a model score. Safety zeros: unauthorized spend, double charge, unapproved action, injection obeyed, secrets in logs | 2026-10-18. Cost from `usage.cost_in_usd_ticks` on the API responses, not a copied price page. Main `d6cb6ff`. Write-up: [live/REPORT.md](live/REPORT.md). |

If a later call omits `cost_in_usd_ticks`, `eval-live` uses `LIVE_INPUT_USD_PER_MILLION`, `LIVE_OUTPUT_USD_PER_MILLION`, and `LIVE_PRICE_DATE` together, or it stops before the next request. Those prices are operator-supplied. This repo does not invent a vendor rate card. CI does not call the model.

Default path cost: zero vendor spend. The micro-USD figures above are arithmetic on the synthetic rate.
