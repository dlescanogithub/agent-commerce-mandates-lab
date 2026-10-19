# Provenance

Nothing in this repository is copied from an employer or from a client engagement.

The shopping mandate, the stub merchant, the ledger, the golden cases, and the docs were written for this repository.

An earlier public demo by the same owner was read for the ideas of a discovery manifest and a signed spending limit. No file was copied from it. This lab does not carry that demo's hosts, paths, or deployment.

## Shared utilities

A few small utilities are adapted from the public repository [agent-runtime-evals](https://github.com/dlescanogithub/agent-runtime-evals), commit `e9c96a3080468a420f2f8809e5b108ea743a7637` (2026-10-18). They are ordinary project files, not a library release.

| Utility | In that repository | In this repository | What changed |
|---|---|---|---|
| Secret scanner | `src/agent_runtime/secretscan.py` | `src/agent_commerce/secretscan.py` | Byte-for-byte copy. |
| Cassette replay | `src/agent_runtime/providers/cassette.py` | `src/agent_commerce/providers/cassette.py` | Same behavior (ignore the request, play the next completion, fail when exhausted). Imports point at this package. |
| JSON trace | `src/agent_runtime/trace.py` | `src/agent_commerce/trace.py` | String fields go through the redactor. |
| Structured logging | `src/agent_runtime/logging_setup.py` | `src/agent_commerce/logging_setup.py` | The formatter redacts messages and extra fields. |
| Backoff | `src/agent_runtime/providers/backoff.py` | `src/agent_commerce/backoff.py` | Same formula and the same 8 second cap. Used here for payment retries, not for model calls. |
| Eval driver shape | `src/agent_runtime/evalkit/suite.py` | `src/agent_commerce/evalkit/suite.py` | Rewritten. Cases are shopping scenarios. Checks are spending invariants, not tool trajectories. |

## Secret scanner

`src/agent_commerce/secretscan.py` is the copy the other portfolio repositories vendor. Keep that file byte-for-byte identical, including this hash. The finding ids name key shapes. They are not a claim of affiliation with any company.

sha256: a3b48e9b7a413d57bbb6e06ef1e3c3194a4100195a61542ad712a87898851709

Check it with `make check-secretscan`. It recomputes the hash of the file bytes and compares it to the line above. A change to the scanner updates the hash in the same commit.
