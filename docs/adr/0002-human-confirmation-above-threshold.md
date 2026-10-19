# 0002. Human confirmation above a threshold, and no approve tool

## Status

Accepted.

## Context

Some purchases are small enough that a signed cap is the control. Some are large enough that a person should see them. If the model has a tool that approves, it will call that tool.

## Decision

`requires_human_above_cents` is part of the signed mandate. `request_payment` returns `human_required` and does not capture when the checkout total is above that line and no approval is on file. The eval harness, or the demo's simulated approver, records `approve` or `reject`. The model has no approve tool. `skip_approval` in the arguments is ignored.

`auto` in a golden case means the simulated approver says yes. It is not the model approving itself.

## Consequences

A cassette that skips the confirmation still cannot capture above the line unless something outside the model recorded an approval first. A reject or an absent approver leaves the ledger at zero for that attempt.
