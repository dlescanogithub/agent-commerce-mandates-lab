# Scope

One category. Office supplies for the fictional company Casa Faro. A household grocery basket is a second scenario on the same mandate code. No fees are stated. There is no statement of work.

## Phase 1 — this repository

Shadow is the cassette suite: the stub shops, the tools decide, nothing leaves the machine.

Then a gate: capture only inside a verified mandate, and a simulated person above the threshold.

Exit criteria for the lab, met on 2026-10-18 by the commands in the README:

- `make eval` passes the 38 cases.
- `make eval-regression` exits non-zero.
- An invalid mandate records zero charges.
- A repeated payment records one charge.
- The secret scanner and the log redactor keep the lab key and the fake card number out of the trace.

Exit criteria for a real pilot, not met here:

- A named human backup who can void.
- A week of shadow on real carts with no capture. Not done. There are no real carts.
- The policy owner signs the mandate. Here the lab signs it with a key it also holds.

## Phase 2 — still design

Add one more category only after new cases exist. Travel booking under a policy and subscription renewals are named in the README as design-only. They need dates, travelers or seats, and a renewal calendar this merchant does not have.

Partial refunds, if the business asks for them, are a new ledger row type and new cases. The current void is full.

## Phase 3 — not this repo

A processor, a wallet, KYC, disputes, FX, merchant onboarding, and a host. The README lists them as design-only. None of those have code.

## Assumptions

- One currency, `LAB`, simulated.
- One open checkout per run.
- The lab clock is the timestamp in the case, not the wall clock.
- The person who confirms is outside the model.
- Catalog prices are fixtures, not a market.

## Out of scope

- Real card numbers, real accounts, real people.
- Hosting on any public platform.
- A conformant AP2 or UCP implementation.
- Multi-currency conversion.
- Chargebacks and representment.
- More than one worker sharing the SQLite file.

## Exit

Stop the pilot if a capture lands without a verified mandate, or if a retry writes a second charge for the same checkout. Those two are the conditions the invariants already treat as failures.
