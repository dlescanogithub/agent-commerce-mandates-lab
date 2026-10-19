# Risks

Owners are roles, not named people. Probability and impact are judgments for this lab, not a measured incident rate.

| Id | Risk | Probability | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Model spends above the cap | Low in this suite (the check is in the tool, and the 38 cases passed on 2026-10-18) | High | Re-check the checkout total against the signed cap in `tools.py`. Invariant `spend_within_cap`. | Runtime |
| R2 | Mandate signature is treated as decoration | Low while verification fails closed | High | HMAC compare, then expiry and allow-lists. Invalid mandate spends zero. | Runtime |
| R3 | Lab HMAC is mistaken for a verifiable credential | Medium if a reader skips the README | High | ADR 0001. The key file is labelled NOT REAL. Docs say this is not AP2-conformant. | Author |
| R4 | Retry double-charges | Low on the fake rail | High | Derived idempotency key, unique in SQLite and on the rail. | Runtime |
| R5 | Payment retry storm | Medium if a caller removes the attempt cap | Medium | `MAX_PAYMENT_ATTEMPTS` default 3. Backoff capped at 8 seconds. Then a dead-letter row. | Runtime |
| R6 | Product text is executed as an instruction | Low in this code (no parser reads descriptions) | High | Injection sentence stays in the catalog payload to the model and out of the trace. Gift-card SKU is not an allowed category. | Runtime |
| R7 | Model raises its own cap | Seen: on 2026-10-18 the live model called `raise_mandate_cap` in 18 and 17 cases. The tool still refused every time | High | Cap is inside the signature. `raise_mandate_cap` is a probe and always returns `cap_is_not_agent_writable`. | Runtime |
| R8 | Card number lands in a log | Low while the formatter redacts | High | Refuse card fields. Redact before write. Invariant `no_secret_in_logs`. | Runtime |
| R9 | Human gate is skipped with an argument | Low (`skip_approval` is ignored) | High | No approve tool. Approval is a ledger row written by the harness. | Runtime |
| R10 | Mandate revoked after the cart exists | The lab handles the flag before capture | Medium | `mandate_revoked` spends zero. A capture that already happened needs the void path and a person. | Operator, via the runbook |
| R11 | Ledger and rail disagree | Low on one process; untested across two | High | Runbook "ledger mismatch". No automatic repair. | Operator |
| R12 | Someone runs the HTTP stub on a public interface | Low (`MERCHANT_HOST` rejects it) | High | Loopback only. Documented in SECURITY.md. | Operator |
| R13 | CI starts calling a paid model | Low (`eval live` does not send; `eval-live` requires `LIVE_ENABLED=1`; CI sets neither) | Medium | ADR 0004 and ADR 0008. The CI job fails if `eval-live` exits 0. | CI owner |
| R14 | A reader treats [EST] labor math as a saving | Medium | Medium | Every such figure is marked [EST]. Measured figures name the command. | Author |

## Not a risk register for a processor

Account takeover, stolen credentials, and scheme disputes are out of scope. There is no instrument to steal.
