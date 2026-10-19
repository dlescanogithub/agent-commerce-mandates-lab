# Runbook

Local lab. One operator. There is no on-call rotation and no host to roll back.

## Operate

```bash
make setup
make demo
make eval
make eval-regression   # exits non-zero on purpose
make eval-live         # exits 2 and sends nothing unless LIVE_ENABLED=1
```

Without `make`:

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m agent_commerce.cli demo
.venv/bin/python -m agent_commerce.evalkit run
.venv/bin/python -m agent_commerce.evalkit regression
.venv/bin/python -m agent_commerce.evalkit eval-live
```

`eval-live` is the only command that can spend. It needs `LIVE_ENABLED=1`, `XAI_API_KEY`, and `MAX_LIVE_SPEND_USD`. It stops before the next request when the cap is reached. Do not export the key into CI.

The demo binds `127.0.0.1` on an ephemeral port, buys two reams, prints JSON, and stops. The work directory defaults to `var/demo` (gitignored).

## Monitor

- JSON logs on stderr. One object per line. Card-like numbers and sensitive field names are redacted.
- One JSONL trace per run under the work directory's `traces/`. Fields: event, tool name, ok, error, token counts. Not product descriptions.
- The live call log (`LIVE_LOG_PATH`, default `var/live/calls.jsonl`) is a different file. Each line is one JSON object. A model call keeps the HTTP and token fields and adds `tool_calls_names`. An executed tool adds a `tool_result` line: `accepted` or `rejected`, the rejection code, and `step` to tie it to the call. No arguments, no result body, no prompt. The run's `summary.json` adds `tool_log` (calls, rejections, and `raise_mandate_cap` after a prior rejection). The definition of "after a rejection" is in [METRICS](METRICS.md). The 2026-10-18 logs under `docs/live/` do not have these fields.
- SQLite ledger: `charges`, `refunds`, `dead_letters`, `decisions`.

There is no dashboard and no OpenTelemetry export.

## Ownership

| Piece | Owner in this lab | Owner in a real pilot |
|---|---|---|
| Mandate contents | The template in `mandate.py` | The spend-policy owner. Not the person who edits the prompt. |
| Approve / reject above the line | The eval harness (`human` on the case) | A named person. The model does not hold this. |
| Ledger file | Whoever can read the work directory | Finance operations. Treat the file like a database. |
| Void | `void_or_refund` on a charge this process stored | The same person, plus the processor if money already moved. Here, money did not move. |
| CI gate | The `ci` job | Whoever can merge. Branch protection is not turned on from this repo. |

## Incident: mandate revoked mid-purchase

What you see: a checkout exists, `request_payment` returns `mandate_revoked`, `charges` is empty.

What the lab does: the runner sets the revoked flag before that tool call when the case asks for it. The tool refuses. No capture.

What you do: leave the cart. Do not retry with a new mandate id to sneak the same cart through. Issue a new signed mandate if the purchase is still wanted, and start a new run. If a charge row already exists, void it and confirm the spent total is back to the previous number.

## Incident: payment retry storm

What you see: several `simulated_timeout` or `simulated_500` attempts, then one `dead_letters` row, and no charge. Or, if a later attempt succeeded, exactly one charge.

What the lab does: at most `MAX_PAYMENT_ATTEMPTS` (3) tries. The delay function caps at 8 seconds. The eval sleeper does not actually sleep. A policy refusal is not retried.

What you do: if dead letters climb because someone set the attempt count to a huge number, put it back to 3 and stop the process. Do not delete the dead-letter rows to "clear" the incident. They are the record.

## Incident: live spend cap mid-suite

What you see: `eval-live` prints `stopped_for_spend_cap=true`. The call log's last rows are HTTP 200, then no further request. Cases not started have no ledger.

What the lab does: the adapter adds `usage.cost_in_usd_ticks` when the response has it. If that field is missing and no dated token price is configured, it treats the cost as unknown and blocks the next request. It does not send the next call to "finish the case".

What you do: leave the partial log. Do not raise the cap inside the same process to squeeze one more case. If you need another sample, start a new run with a new cap and say how many cases finished. Do not paste the API key into the log or the report.

## Incident: ledger mismatch

What you see: the merchant order says `paid` and the ledger has no row, or the ledger has a row and the order is still `open`.

What the lab does: both writes happen in one process, in `_record_capture`, after the rail returns ok. A crash between those two lines can disagree. There is no repair job.

What you do: do not insert a charge by hand to "fix" the file. Void on the merchant side if it shows paid, and start a new run with a new checkout. Two processes must not share one SQLite file.

## Rollback

This lab has no deployment. Rollback is `git checkout` of the previous revision and a new demo directory. Do not reuse a ledger file from a bad run as if it were empty.

If a future host exists, the rollback is the previous revision plus a stop on new captures. Voids for captures that already happened are a person's job. This repo cannot demonstrate that host.

## Handoff

Give the next person: this runbook, `SECURITY.md`, the mandate templates, and the command that last went green. Do not hand them a filled `.env` or a `lab_hmac.key`. The key is generated again on the next run.
