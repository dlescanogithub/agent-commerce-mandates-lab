"""Lab HMAC keys. Generated per run. Not a credential for any network.

The file is labelled NOT REAL. A production mandate would use an asymmetric
credential the merchant can verify without holding the user's signing key.
This process holds both sides because both sides are the lab.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LabKey:
    """One symmetric key. ``path`` is None when the caller passed the bytes in."""

    material: bytes
    path: Path | None
    temporary: tempfile.TemporaryDirectory[str] | None

    def hex(self) -> str:
        return self.material.hex()

    def close(self) -> None:
        if self.temporary is not None:
            self.temporary.cleanup()
            self.temporary = None


def generate_lab_key(directory: Path | None = None) -> LabKey:
    """Write a fresh 32-byte key. The directory is created if needed.

    When ``directory`` is omitted, the key lives in a temporary directory
    that the caller closes. Nothing is written under a fixed home path.
    """

    material = secrets.token_bytes(32)
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if directory is None:
        temporary = tempfile.TemporaryDirectory(prefix="lab-keys-")
        directory = Path(temporary.name)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "lab_hmac.key"
    path.write_bytes(material)
    os.chmod(path, 0o600)
    notice = directory / "NOT_REAL.txt"
    notice.write_text(
        "LAB KEY — NOT REAL.\n"
        "Generated at runtime for this process only.\n"
        "Not a credential, not a wallet, not for any payment network.\n",
        encoding="utf-8",
    )
    return LabKey(material=material, path=path, temporary=temporary)
