# Discovery

Ten questions to ask before copying this lab into a real buying desk. Casa Faro, below, is fictional. The answers are examples of how the design would move. They are not a transcript.

## 1. Who owns the spend policy?

If procurement owns the cap and finance owns the payment instrument, the mandate is signed by the policy owner and the rail is owned by finance. This lab has one process doing both, which is only acceptable because both sides are fake. Split them before any real instrument exists.

## 2. What is the cap, in which currency, and over what window?

The office sample is 20000 simulated LAB cents, one mandate, one expiry. A weekly grocery cap is a different template (`grocery`), not a currency conversion. If the answer is "it depends on the team", the mandate id has to be per team. This repo has two templates and no team directory.

## 3. Which merchants and which categories are allowed?

The office mandate names `mercado-ficticio` and `office_supplies`. A second fictional merchant, Bazar Inventado, is refused. If the real list changes every week, the signature has to be re-issued. A mutable list outside the signature is a hole. This lab refuses a body that does not match the signature.

## 4. Is the per-item max a unit price or a line total?

Here it is the unit price. Eleven reams of paper are allowed because each ream is under the max and the cart is under the cap. One toner cartridge is refused on unit price even though the cap would hold it. If the business means "line total", the check in `tools.py` changes and the toner case is rewritten first.

## 5. Where is the human line, and who may stand above it?

Office sample: 5000 simulated LAB cents. The model cannot approve. If the answer is "the buyer's manager, and only inside business hours", the simulated `auto` approver in the golden set is the wrong stand-in. You would add an identity and a clock. Neither is in this repo.

## 6. What happens when a mandate is revoked mid-purchase?

The lab sets a flag after checkout and before capture. Capture returns `mandate_revoked` and writes no charge. If the real answer is "also void a capture that already landed", that is the refund path plus a person. The lab can void a charge it just made. It does not talk to a network.

## 7. What fraud and abuse are in scope?

In scope here: over-cap carts, merchants outside the list, expired or forged signatures, a self-raised cap, a repeated payment, a card number in the arguments, and a product description that says to ignore the mandate. Out of scope: account takeover, stolen instruments, friendly fraud, and a model that colludes with a compromised merchant. Those need an identity provider and a real rail.

## 8. What does the payment provider require?

This rail wants an idempotency key the tool chooses, and it fails with timeout or HTTP 500 so the retry policy can be tested. A real provider will have its own key rules, its own status codes, and a capture that can succeed after the client has already timed out. The dead-letter table is the place a person looks. It is not a reconciliation file from a processor.

## 9. Who handles a dispute or a refund?

`void_or_refund` voids the one charge this process stored. There is no chargeback, no partial refund, and no evidence pack for a card network. If the answer is "the processor owns disputes", this tool should open a case, not pretend to settle it. That case object is not built.

## 10. What does success look like in the first month?

This repo can show, on the stub: completed inside the mandate, zero spend when the mandate is invalid, and a red forced regression. A real pilot would add: share of carts a person approved without an edit, escalations per 100 orders, dead letters per 100 payments, and cost per completed order including the person's minutes. Those counters are defined in [METRICS.md](METRICS.md). They are empty. The stub suite is not that month.
