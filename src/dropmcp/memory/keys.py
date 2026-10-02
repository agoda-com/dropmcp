"""Short public memory keys such as ``MEM-7K3F9Q``.

Five random characters from an alphabet without look-alikes, plus a Luhn mod N
check character, so a key mangled by summarisation is detected rather than
resolved to the wrong memory.
"""

from __future__ import annotations

import re
import secrets

KEY_PREFIX = "MEM-"
KEY_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
_BODY_LENGTH = 5
_KEY_RE = re.compile(rf"^{KEY_PREFIX}([{KEY_ALPHABET}]{{{_BODY_LENGTH + 1}}})$")


def _check_char(body: str) -> str:
    base = len(KEY_ALPHABET)
    total = 0
    factor = 2
    for char in reversed(body):
        addend = factor * KEY_ALPHABET.index(char)
        total += addend // base + addend % base
        factor = 1 if factor == 2 else 2
    return KEY_ALPHABET[(base - total % base) % base]


def new_key() -> str:
    body = "".join(secrets.choice(KEY_ALPHABET) for _ in range(_BODY_LENGTH))
    return f"{KEY_PREFIX}{body}{_check_char(body)}"


def is_valid_key(text: str) -> bool:
    match = _KEY_RE.match(text.strip().upper()) if isinstance(text, str) else None
    if match is None:
        return False
    chars = match.group(1)
    return _check_char(chars[:-1]) == chars[-1]
