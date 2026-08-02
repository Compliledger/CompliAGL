"""Deterministic canonicalization and hashing for the canonical AIProof.

An AIProof must be **independently** re-serializable to exactly the same bytes
by any verifier, so its hash and signature can be reproduced without trusting
CompliAGL. This module implements the
`RFC 8785 JSON Canonicalization Scheme (JCS)`_ over the JSON value domain used by
AIProofs (objects, arrays, strings, integers, finite numbers, booleans, null)
and exposes the algorithm identifiers that every AIProof records alongside its
hash.

Design notes
------------

* **Object member ordering** follows RFC 8785: keys are sorted by their UTF-16
  code units. AIProof keys are ASCII, so this coincides with code-point order,
  but the UTF-16 ordering is implemented explicitly for correctness.
* **Strings** use the RFC 8785 / RFC 8259 minimal escaping set.
* **Numbers**: AIProofs carry monetary amounts as integer *minor units* plus a
  currency code, so canonical numbers are integers in practice. Finite floats
  are still serialized via a documented shortest round-trip form; ``NaN`` /
  ``Infinity`` are rejected because they are not valid JSON.

.. _RFC 8785 JSON Canonicalization Scheme (JCS):
   https://www.rfc-editor.org/rfc/rfc8785
"""

from __future__ import annotations

import hashlib
from typing import Any

# Documented, versioned algorithm identifiers recorded inside every AIProof so a
# verifier knows exactly how to reproduce the hash and signature input.
CANONICALIZATION_ALGORITHM = "JCS/RFC8785"
HASH_ALGORITHM = "SHA-256"

# RFC 8785 §3.2.2.2 two-character escapes for the C0 control characters that
# have a short form. All other control characters use the ``\u00xx`` form.
_SHORT_ESCAPES = {
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
    '"': '\\"',
    "\\": "\\\\",
}


def _escape_string(value: str) -> str:
    """Return *value* escaped as a canonical JSON string literal (with quotes)."""
    out = ['"']
    for ch in value:
        if ch in _SHORT_ESCAPES:
            out.append(_SHORT_ESCAPES[ch])
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _serialize_number(value: float) -> str:
    """Serialize a finite JSON number deterministically.

    Integers are emitted without a decimal point. Finite non-integral floats use
    Python's shortest round-trip ``repr`` (which, like RFC 8785, is derived from
    the shortest decimal that round-trips to the IEEE-754 double).
    """
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("NaN and Infinity are not valid canonical JSON numbers")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return repr(value)


def _sorted_items(obj: dict[str, Any]) -> list[tuple[str, Any]]:
    """Return object members ordered by their UTF-16 code units (RFC 8785)."""
    return sorted(obj.items(), key=lambda kv: str(kv[0]).encode("utf-16-be"))


def _canonicalize(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _escape_string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _serialize_number(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonicalize(item) for item in value) + "]"
    if isinstance(value, dict):
        members = (
            _escape_string(str(key)) + ":" + _canonicalize(val)
            for key, val in _sorted_items(value)
        )
        return "{" + ",".join(members) + "}"
    raise TypeError(f"Value of type {type(value).__name__!r} is not JSON-canonicalizable")


def canonicalize(value: Any) -> str:
    """Return the RFC 8785 canonical JSON string for *value*."""
    return _canonicalize(value)


def canonical_bytes(value: Any) -> bytes:
    """Return the UTF-8 encoded canonical JSON bytes for *value*."""
    return canonicalize(value).encode("utf-8")


def sha256_hex(value: Any) -> str:
    """Return the lowercase hex SHA-256 of *value*'s canonical serialization."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_hex_bytes(data: bytes) -> str:
    """Return the lowercase hex SHA-256 of raw *data* bytes."""
    return hashlib.sha256(data).hexdigest()
