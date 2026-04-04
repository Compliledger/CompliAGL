"""Hashing utilities for proof bundles and audit integrity."""

import hashlib
import json
from typing import Any


def sha256_hash(data: str) -> str:
    """Return the hex-encoded SHA-256 hash of *data*."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hash_dict(payload: dict[str, Any]) -> str:
    """Deterministically hash a dictionary by sorting its keys."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_hash(canonical)


def compute_bundle_hash(
    *,
    module: str,
    entity_id: str,
    rule_version_used: str,
    decision_result: str,
    evaluation_context: Any,
    reason_codes: Any,
    timestamp: str,
) -> str:
    """Compute a deterministic SHA-256 hash for a proof bundle.

    The canonical payload is built from the specified fields using stable
    JSON serialization with sorted keys and compact separators.
    """
    canonical_payload = {
        "module": module,
        "entity_id": entity_id,
        "rule_version_used": rule_version_used,
        "decision_result": decision_result,
        "evaluation_context": evaluation_context,
        "reason_codes": reason_codes,
        "timestamp": timestamp,
    }
    canonical = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_hash(canonical)
