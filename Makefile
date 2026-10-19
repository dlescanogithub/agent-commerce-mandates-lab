.PHONY: setup demo test eval eval-regression eval-live lint format check-secretscan

PYTHON := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e ".[dev]"
	.venv/bin/pre-commit install

demo:
	$(PYTHON) -m agent_commerce.cli demo

test:
	$(PYTHON) -m pytest --cov-fail-under=80

eval:
	$(PYTHON) -m agent_commerce.evalkit run

# Expected to exit non-zero. CI fails the job if this exits 0.
eval-regression:
	$(PYTHON) -m agent_commerce.evalkit regression

# Sends only when LIVE_ENABLED=1. Off by default. CI does not set it.
eval-live:
	$(PYTHON) -m agent_commerce.evalkit eval-live

lint: check-secretscan
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy
	$(PYTHON) -m agent_commerce.secretscan

check-secretscan:
	$(PYTHON) -c 'import hashlib,re; from pathlib import Path; digest=hashlib.sha256(Path("src/agent_commerce/secretscan.py").read_bytes()).hexdigest(); text=Path("docs/PROVENANCE.md").read_text(encoding="utf-8"); found=re.search(r"(?m)^sha256: ([0-9a-f]{64})$$", text); assert found and found.group(1)==digest, digest; print("secretscan sha256 ok")'

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .
