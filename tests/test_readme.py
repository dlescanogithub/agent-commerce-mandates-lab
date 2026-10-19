"""README shape, plus a hygiene scan that does not name any person or organization."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_commerce.secretscan import scan_repo

ROOT = Path(__file__).resolve().parents[1]

HEADINGS = (
    "## Problem and result",
    "## Demo",
    "## Business case",
    "## Architecture",
    "## Results",
    "## Use cases, governance and business strategy",
    "## Decisions",
    "## Security and known limits",
    "## How to reproduce",
    "## Next steps",
    "## Where to go next in the docs",
)

_SKIP = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "var",
}


def _generic_hazards() -> tuple[str, ...]:
    """Local paths, hosting hostnames, and pages hosts. Built so this file can be scanned."""

    return (
        "/home" + "/",
        "rail" + "way",
        "fly" + ".dev",
        "github" + ".io",
    )


def _extra_terms() -> tuple[str, ...]:
    """Terms from BANNED_TERMS_FILE. Unset by default, and that file is never committed."""

    raw = os.environ.get("BANNED_TERMS_FILE", "").strip()
    if not raw:
        return ()
    path = Path(raw)
    if not path.is_file():
        raise AssertionError("BANNED_TERMS_FILE is set but does not name a file")
    terms: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        term = line.strip()
        if not term or term.startswith("#"):
            continue
        terms.append(term)
    return tuple(terms)


def _hits(terms: tuple[str, ...]) -> list[str]:
    folded = [(term, term.casefold()) for term in terms if term.strip()]
    found: list[str] = []
    for path in _files():
        try:
            text = path.read_text(encoding="utf-8").casefold()
        except (UnicodeDecodeError, OSError):
            continue
        for term, needle in folded:
            if needle in text:
                found.append(f"{path.relative_to(ROOT)}:{term}")
    return found


def _files() -> list[Path]:
    found: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP for part in path.parts):
            continue
        found.append(path)
    return found


def test_readme_section_order_and_hygiene() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    indexes = [text.index(heading) for heading in HEADINGS]
    assert indexes == sorted(indexes)
    assert "What this does NOT do" in text
    assert "Lab with fake providers" in text
    assert _hits(_generic_hazards() + _extra_terms()) == []
    assert scan_repo(ROOT) == []


def test_extra_deny_list_is_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BANNED_TERMS_FILE", raising=False)
    assert _extra_terms() == ()

    commented = tmp_path / "commented.txt"
    commented.write_text("# ignored\n\n", encoding="utf-8")
    monkeypatch.setenv("BANNED_TERMS_FILE", str(commented))
    assert _extra_terms() == ()
    assert _hits(_extra_terms()) == []

    listed = tmp_path / "listed.txt"
    listed.write_text("Mercado Ficticio\n", encoding="utf-8")
    monkeypatch.setenv("BANNED_TERMS_FILE", str(listed))
    assert _hits(_extra_terms())

    monkeypatch.setenv("BANNED_TERMS_FILE", str(tmp_path / "missing.txt"))
    with pytest.raises(AssertionError, match="does not name a file"):
        _extra_terms()
