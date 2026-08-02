"""Canonical CompliAGL AIProof subsystem.

The single, canonical proof implementation for CompliAGL: schema, RFC 8785
canonicalization, SHA-256 hashing, digital signing, local verification,
persistence, versioned JSON Schema, and the formal CompliLedger handoff.
"""

from __future__ import annotations

from app.services.canonical.aiproof.canonicalization import (
    CANONICALIZATION_ALGORITHM,
    HASH_ALGORITHM,
    canonicalize,
    sha256_hex,
)
from app.services.canonical.aiproof.generator import (
    build_aiproof,
    compute_aiproof_hash,
    compute_component_hashes,
    generate_signed_aiproof,
    sign_aiproof,
)
from app.services.canonical.aiproof.handoff import (
    CompliLedgerHandoff,
    HandoffResult,
    build_handoff_payload,
    get_handoff,
)
from app.services.canonical.aiproof.json_schema import (
    AIPROOF_SCHEMA_ID,
    aiproof_json_schema,
    validate_against_schema,
)
from app.services.canonical.aiproof.verify import (
    AIProofVerification,
    verify_aiproof,
)

__all__ = [
    "CANONICALIZATION_ALGORITHM",
    "HASH_ALGORITHM",
    "canonicalize",
    "sha256_hex",
    "build_aiproof",
    "sign_aiproof",
    "generate_signed_aiproof",
    "compute_aiproof_hash",
    "compute_component_hashes",
    "verify_aiproof",
    "AIProofVerification",
    "build_handoff_payload",
    "get_handoff",
    "CompliLedgerHandoff",
    "HandoffResult",
    "aiproof_json_schema",
    "validate_against_schema",
    "AIPROOF_SCHEMA_ID",
]
