"""Hashing utilities for proof generation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_hash(data: Any) -> str:
    """Return the SHA-256 hex digest of *data*.

    *data* is first serialised to a canonical JSON string (sorted keys,
    no extra whitespace) before hashing.
    """
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
