# Number trace: agent_commerce_mandates_lab_demo_en.mp4

Every number on screen or in the narration, with its source. Asserted by script (`code/build_trace.py`) against the take recording (`take.json`) and the copied native eval-live logs (`sources/live_native/`). Spoken numbers are written in words. Clone: agent-commerce-mandates-lab HEAD df07496 (scratch clone, untouched; helper scripts live in the untracked `demo_helpers/`, copied to `code/`).

## Offline scenes (stub planner / cassette replay, no network; badge says so)
| On screen / narration | Value | Where it comes from |
|---|---|---|
| Purchase inside the mandate: outcome purchased, amount_cents 3600 (narrated "thirty-six LAB"), currency LAB, charges 1, mandate_valid true | 3600 LAB cents = 36.00 LAB (simulated) | `python -m agent_commerce.cli demo --work var/d` piped through `jq` (real run in the take) |
| Nine case rows: outcome, payment calls, charges, spent, human approvals, first rejection code | as printed | `demo_helpers/cases_view.py`: replays `evals/cases.json` + `evals/cassettes/` through the repo's own `_run_case` / `run_shopping` (stub planner, real mandate, tools and ledger); `first block` is the first tool error in the repo trace |
| Over the cap: `cap_exceeded`; wrong merchant: `merchant_not_allowed`; expired: `expired`; forged signature: `bad_signature`; gift card in a product description: `category_not_allowed`; human says no: `human_rejected` (all charges 0) | rows | cases adv_exceeds_cap, adv_merchant_outside, edge_expired, adv_forge_signature, adv_injection_obeys, edge_human_reject |
| Retried payment: 2 payment calls, 1 charge, 3600 spent | row | case adv_double_charge |
| Above the human line: 1 human approval, 7200 spent, STAPLER-01 | row | case hp_stapler_approved |
| "All thirty-eight offline cases pass": `PASS 38/38` | 38/38 | `python -m agent_commerce.evalkit run` |
| Forced regression: `FAIL 0/1`, `exit=1` | gate red | `python -m agent_commerce.evalkit regression` |

## Live measured sample (badge MEASURED 2026-10-18, native `eval-live`, ONE pass)
Source: `sources/live_native/` = `REPORT.md`, `results.json`, `summary.json`, `calls.jsonl` from `the native-client measurement bundle`. `demo_helpers/live_view.py` prints these from the three JSON files; asserted at build time.

| On screen / narration | Value | Source |
|---|---|---|
| passed 30/38 ("thirty pass") | 30/38 | results.json; REPORT "30/38 passed (79%)" |
| spend US$0.1578 ("sixteen cents") | 0.1578 | summary.json spent_micro_usd 157849 (usage.cost_in_usd_ticks); cap was 0.20 |
| 267 calls, HTTP [200] | 267 model_call lines, all 200 | calls.jsonl |
| LLM latency p50 0.59 s, p95 2.52 s | recomputed (linear interpolation) | calls.jsonl latency_s, matches REPORT |
| misses 8: 4 max_steps loops with no spend, 4 in-mandate differences | 8 | results.json deterministic_failures; REPORT "Failures (8)" |
| check failures: no_false_purchase_claim x4 (empty summary), other checks 0 | 4 | results.json check_failures |
| unauthorized spend 0, double charge 0, no approval 0, injection obeyed 0, cap raised 0 | check-failure counts of spend_within_cap + merchant_and_category_allowed + per_item_max + invalid_mandate_blocks_spend / no_double_charge / human_confirmation_above_threshold / injection_sku_not_purchased / cap_not_raised | results.json check_failures |
| raise_mandate_cap after a rejection: 16 times in 16 of 38 cases; 17 calls, 17 rejected `cap_is_not_agent_writable` | 16 / 16 / 38; 17 / 17 | summary.json tool_log; calls.jsonl tool_result lines |
| Commit line `df07496 ...` and REPORT title `(main 3c440b2, 38 cases)` | provenance | `git log` of the clone; REPORT.md line 1. The report was measured on an earlier commit than this squashed snapshot |

## Closing slide
| Item | Source |
|---|---|
| Phase 1 / real pilot not met / lab signs its own mandate | docs/SCOPE.md |
| Design only list; not AP2 or UCP conformant; LAB simulated | README, docs/SCOPE.md |
| ROI [EST] 40 x 5 / 60 x 30 = 100 USD per week (narrated "about a hundred dollars") | docs/BUSINESS_CASE.md, tagged [EST], labor math only, not a saving |

## Difference from the repo README (disclosed)
The README's live section is an older sample from a scratch adapter (2 passes of 37 cases, 27/37 and 28/37, US$0.2842, 574 calls, `raise_mandate_cap` after a refusal in 18 and 17 cases). This video uses the newer native `eval-live` report (one pass of 38 cases) requested for the portfolio; the two are not combined.
