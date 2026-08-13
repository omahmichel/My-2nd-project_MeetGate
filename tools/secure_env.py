from __future__ import annotations

import base64
import os
from io import StringIO
from pathlib import Path

from dotenv import dotenv_values


def _load_values(text: str) -> None:
    values = dotenv_values(stream=StringIO(text))

    for key, value in values.items():
        if key and value is not None:
            os.environ.setdefault(key, value)


def load_secure_environment(base_dir: Path) -> None:
    encrypted_path = Path(base_dir) / ".env.enc"
    plaintext_path = Path(base_dir) / ".env"

    if encrypted_path.exists():
        if os.name != "nt":
            return

        import win32crypt

        encrypted_blob = base64.b64decode(
            encrypted_path.read_bytes()
        )
        decrypted_result = win32crypt.CryptUnprotectData(
            encrypted_blob,
            None,
            None,
            None,
            0,
        )

        if (
            not isinstance(decrypted_result, tuple)
            or len(decrypted_result) < 2
            or not isinstance(decrypted_result[1], (bytes, bytearray))
        ):
            raise RuntimeError(
                "Unexpected CryptUnprotectData return format."
            )

        _load_values(bytes(decrypted_result[1]).decode("utf-8"))
        return

    if plaintext_path.exists():
        _load_values(
            plaintext_path.read_text(encoding="utf-8")
        )
