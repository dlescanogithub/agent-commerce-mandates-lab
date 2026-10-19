# Security

This is a local lab. It is not a hosted service and it does not move real money.

## Secrets

- No API keys, tokens, or private keys belong in the repo.
- `.env.example` lists variables and leaves keys empty. `eval live` does not send. `make eval-live` sends only when `LIVE_ENABLED=1`, and the key is `XAI_API_KEY`. CI sets neither. The call log records status, latency, tokens, and cost. It does not record the prompt or the key.
- The process reads configuration from the environment. The stub planner is the default and needs no key.
- Lab HMAC keys are generated per run into a temporary directory, or into `LAB_KEY_DIR` when that variable is set. The directory contains `NOT_REAL.txt`. The key file mode is `0600`. Do not commit it. `var/` is gitignored.
- CI runs two scanners: `python -m agent_commerce.secretscan` and gitleaks 8.30.1. The gitleaks tarball is checked against a pinned SHA-256 before it runs. Either scanner failing fails the `ci` job.
- `src/agent_commerce/secretscan.py` is the copy shared with the public portfolio repository [agent-runtime-evals](https://github.com/dlescanogithub/agent-runtime-evals). `docs/PROVENANCE.md` records its sha256. `make check-secretscan` recomputes that hash. The finding ids name key shapes. They are not a claim of affiliation with any company.

## What the model is not allowed to do

- It has no approve tool. `skip_approval` in the arguments is ignored.
- It does not choose the idempotency key. The tool derives `mandate_id:checkout_id`.
- It does not choose the amount. The checkout total is what the rail captures.
- It cannot raise `cap_cents`. `raise_mandate_cap` always returns `cap_is_not_agent_writable`.
- Card-like fields (`pan`, `card`, `cvv`) are refused. The lab rail does not accept card numbers.
- A product description is data. The runner does not parse it for instructions.
- Verification of a mandate fails closed: bad signature, tampered body, missing signature, expiry, or a foreign key all spend zero.
- INFO logs and JSONL traces go through the redactor. Catalog descriptions are not written to either one.

## The merchant HTTP server

`python -m agent_commerce.cli demo` binds `127.0.0.1` only. `MERCHANT_HOST` rejects any other host. There is no public route and no authentication, because the process is not a service. Do not put it on a public interface.

## CI and branch protection

GitHub Actions workflow `.github/workflows/ci.yml` runs one job, `ci`, after a single install:

| Step | What it runs |
|---|---|
| lint | `ruff check`, `ruff format --check` |
| typecheck | `mypy` (strict on `agent_commerce`) |
| test | `pytest` with coverage, floor 80 percent, and the percent written to the job summary |
| eval | cassette suite, which must pass, and the forced regression, which must fail |
| secrets | the Python scanner and gitleaks 8.30.1, checksum pinned |

This repository does not enable branch protection. That is a setting on the GitHub repository, and turning it on is a human action. Before `main` accepts merges, require the `ci` job and at least one review from someone who did not write the change. Do not allow force-pushes to `main`.

## Dependency pinning

Runtime dependencies: none. Dev tools are pinned in `pyproject.toml` (`ruff==0.17.1`, `mypy==2.4.0`, `pytest==9.1.1`, `pytest-cov==7.1.0`, `coverage==7.16.2`, `pre-commit==4.7.0`). The Docker image is `python:3.12-slim`. Actions are pinned to major tags (`actions/checkout@v4`, `actions/setup-python@v5`). Pinning those tags to commit SHAs is a reasonable next step, not done here.

## Reporting

This is a portfolio repository, not a production service. There is no security bounty. If you are reading it as a reviewer, the interesting question is whether a new tool can spend without a mandate check and, above the threshold, without a recorded human decision.
