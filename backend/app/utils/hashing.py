"""Hashing utilities for proof bundles and audit integrity."""

import hashlib
import json
from typing import Any


def sha256_hash(data: str) -> str:
    """Return the hex-encoded SHA-256 hash of *data*."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hash_dict(payload: dict[str, Any]) -> str:
    """Deterministically hash a dictionary by sorting its keys."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return sha256_hash(canonical)
