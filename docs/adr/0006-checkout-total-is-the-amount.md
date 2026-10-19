# 0006. The checkout total is the amount

## Status

Accepted.

## Context

If the model picks the amount, a prompt can ask for a number the cart does not support, or a number the mandate does not allow, and a careless tool will pass it to the rail.

## Decision

`request_payment` ignores any amount in the arguments. It loads the open checkout and uses that total. The mandate is checked again at that moment: merchant, category, per-item unit price, remaining cap, currency `LAB`, signature, expiry, and revocation. A price change between the first checkout and the second is the merchant's new total. If the new total is outside the mandate, nothing is captured.

## Consequences

A cassette that says "pay 1 cent" for a 3600-cent cart does not get a 1-cent charge. The golden price-change cases cover a total that still fits and a total that does not.
