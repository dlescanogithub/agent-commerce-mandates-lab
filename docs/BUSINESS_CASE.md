# Business case

Casa Faro is a fictional company. It buys office supplies. Mercado Ficticio is a fictional merchant. Amounts in `LAB` are simulated. Nothing here is a quote, a wage, or a vendor bill.

## Problem

A person still builds the cart. The risk is not that the task is slow. The risk is an assistant that can spend outside a signed limit: the wrong merchant, a category nobody allowed, a retry that charges twice, or a product description that tries to talk the model into a gift card.

The lab shows one category, office supplies, under a signed cap. Household groceries are a second scenario on the same code, not a second product.

## What the pilot would change

The assistant may search and build a cart. Capture happens only when the mandate verifies. Above a threshold, a person confirms. Below it, the cap, the merchant list, the category list, and the per-item max are the control. Every capture has an idempotency key. A dead-end payment is a row in a dead-letter table, not a silent retry loop.

## ROI model [EST]

Illustrative labor math. Not a measured saving.

| Input | Value | Label |
|---|---|---|
| Assisted orders | 40 per week | [EST] |
| Minutes a buyer spends today, per order | 6 | [EST] |
| Minutes left when the assistant prepares the cart and a person only confirms the ones above the line | 1 | [EST] |
| Minutes avoided per order | 5 | [EST], the difference of the two rows above |
| Loaded labor | 30 USD per hour | [EST], not a wage quote |
| Hours avoided | 40 × 5 / 60 = 3.33 | [EST] |
| Labor figure | 3.33 × 30 = 100 USD per week | [EST] |

The model bill is not in that 100. A separate xAI sample on 2026-10-18 cost US$0.2842 for 574 calls ([live/REPORT.md](live/REPORT.md)). That sample is not a cost per order and it is not a saving. The stub price of one demo purchase, measured 2026-10-18, version 0.1.0, command `.venv/bin/python -m agent_commerce.cli demo --work /tmp/mandate-demo`, is **273 micro-USD**. The stub price of the whole 38-case suite the same day, command `.venv/bin/python -m agent_commerce.evalkit run`, is **10302 micro-USD**. Both use the synthetic rate in [COST.md](COST.md). They are not a vendor invoice and they are not a saving.

A single capture outside the cap costs more than a year of that stub bill. The case for the control is the avoided bad capture, not the labor line. The labor line is only there so a conversation has a shape.

## What this does not claim

- No production volume, no production saving, no customer.
- No comparison against a real buyer's desk.
- The 100 USD per week [EST] moves as soon as any input moves. It is arithmetic on placeholders.
