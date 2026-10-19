# 0001. HMAC lab signatures, not verifiable credentials

## Status

Accepted. Lab only.

## Context

Public descriptions of agent payment mandates talk about cryptographically signed instructions: a cap, an expiry, and enough context that a merchant can see what the user allowed. Those descriptions also mention verifiable credentials. This lab needs a check that fails closed when the bytes change. It does not need a credential format.

## Decision

A mandate is a fixed set of fields serialized as canonical JSON and signed with HMAC-SHA256. The key is 32 random bytes generated when the run starts, written to a temp directory, and labelled NOT REAL. The same process signs and verifies, because both sides of the lab are this process. A bad signature, a missing signature, a tampered body, or a key this process did not generate makes the mandate invalid. Invalid mandates spend zero.

## Consequences

The check is real against the bytes it signs. It is not a demonstration that a merchant who does not hold the user's key can verify a credential. Ed25519 and SD-JWT are the public direction to study before any real integration. They are not implemented here.
