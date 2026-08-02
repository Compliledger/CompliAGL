"""AIProof generator — assemble, hash and sign the canonical AIProof.

The generator takes the canonical projections of a governed outcome, computes a
per-component hash for each present projection, binds them into the immutable
proof content, computes the deterministic ``aiproof_hash`` (SHA-256 over the RFC
8785 canonical content), and optionally signs that hash.

The proof content is self-describing: the canonicalization + hash algorithm
identifiers, the issuer, and the signer key id are all part of the hashed
content, so any verifier can reproduce the hash and check the signature.
"""

from __future__ import annotations

from typing import Any

from app.services.canonical.aiproof import signing
from app.services.canonical.aiproof.canonicalization import (
    CANONICALIZATION_ALGORITHM,
    HASH_ALGORITHM,
    sha256_hex,
)
from app.schemas.canonical.aiproof import (
    AIProof,
    AIProofStatus,
)

# Projection fields that contribute an individual component hash. Each present
# (non-empty) projection is hashed on its own so a verifier can localize which
# component changed if the top-level hash differs.
_COMPONENT_FIELDS: tuple[str, ...] = (
    "metadata",
    "actor_identity",
    "intent",
    "target",
    "operational_context",
    "governance_packages",
    "policy_resolution",
    "applicability_evaluations",
    "applicable_controls",
    "evidence_requirements",
    "evidence_references",
    "evidence_validation_results",
    "canonical_evidence_package",
    "evidence_sufficiency",
    "control_evaluations",
    "assessment",
    "decision",
    "findings",
    "remediation_lineage",
    "execution_authorization",
    "external_execution_result",
    "timestamps",
)


def compute_component_hashes(proof: AIProof) -> dict[str, str]:
    """Return the per-component canonical hash map for *proof*.

    Empty / absent projections (``None`` or empty list) are skipped so the map
    only records components that are actually present in the proof.
    """
    dumped = proof.model_dump(mode="json")
    hashes: dict[str, str] = {}
    for field in _COMPONENT_FIELDS:
        value = dumped.get(field)
        if value in (None, [], {}):
            continue
        hashes[field] = sha256_hex(value)
    return hashes


def compute_aiproof_hash(proof: AIProof) -> str:
    """Return the deterministic SHA-256 hash of *proof*'s canonical content."""
    return sha256_hex(proof.hashable_content())


def build_aiproof(
    *,
    signer_key_id: str | None = None,
    issuer: str | None = None,
    **content: Any,
) -> AIProof:
    """Build a ``GENERATED`` (unsigned) AIProof with component + proof hashes.

    ``content`` supplies the canonical projections (metadata, actor_identity,
    intent, decision, ...). The issuer and signer key id default to the
    configured AIProof signer; both are bound into the hashed content.
    """
    content.setdefault("canonicalization_algorithm", CANONICALIZATION_ALGORITHM)
    content.setdefault("hash_algorithm", HASH_ALGORITHM)
    proof = AIProof(
        status=AIProofStatus.GENERATED,
        issuer=issuer or signing.issuer(),
        signer_key_id=signer_key_id or signing.active_signer_key_id(),
        **content,
    )
    # Component hashes are part of the hashed content: compute them first, then
    # bind them and compute the top-level proof hash over the full content.
    proof.component_hashes = compute_component_hashes(proof)
    proof.aiproof_hash = compute_aiproof_hash(proof)
    return proof


def sign_aiproof(proof: AIProof) -> AIProof:
    """Sign *proof*'s ``aiproof_hash`` and mark it ``SIGNED``.

    The proof hash is recomputed to guarantee the signature covers the current
    content; a signature over a stale hash can never be produced.
    """
    proof.aiproof_hash = compute_aiproof_hash(proof)
    key_id, signature = signing.sign(proof.aiproof_hash, proof.signer_key_id)
    proof.signer_key_id = key_id
    proof.signature = signature
    proof.status = AIProofStatus.SIGNED
    return proof


def generate_signed_aiproof(
    *,
    signer_key_id: str | None = None,
    issuer: str | None = None,
    **content: Any,
) -> AIProof:
    """Build and sign an AIProof in one step (``SIGNED`` status)."""
    proof = build_aiproof(signer_key_id=signer_key_id, issuer=issuer, **content)
    return sign_aiproof(proof)
