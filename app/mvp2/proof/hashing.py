"""Deterministic hashing utilities for proof generation."""

import hashlib
import json


def sha256_json(data: dict) -> str:
    """Return the SHA-256 hex digest of a deterministic JSON serialization.

    The dictionary is serialized with sorted keys and compact separators
    (``","`` / ``":"``) to guarantee a stable, reproducible hash.
    """
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
