# Adapt this to a real client

Short version. No client is attached to this repo.

Keep:

- A signed spend limit the model cannot edit.
- Fail closed on a bad signature or an expiry.
- The amount taken from the merchant total at pay time.
- An idempotency key the tool chooses.
- A human decision, recorded outside the model, above a threshold.
- Invariant checks on effects, plus a regression that must fail.
- Redaction before any log line.

Replace, and do not pretend this repo already did:

- HMAC with a key this process holds, for a credential the merchant can verify without that key.
- The fake rail, for the processor the client already has. Learn their idempotency rules before writing a second one.
- The simulated approver, for the client's identity and the actual person who may say yes.
- The pinned lab clock, for the system clock.
- `LAB` and the fixture catalog, for their currency and their catalog.
- SQLite, if more than one worker will capture.

Do this in order: discovery questions in [DISCOVERY.md](DISCOVERY.md), shadow with no capture, then the gate, then one category. Stop if a capture lands without a verified mandate.

The office-supplies story (Casa Faro, fictional) is the only implemented shape. Travel, subscriptions, and gift shopping in the README are sketches. Build cases before building tools.
