"""Canonical AIProof service — persist, retrieve, verify, hand off.

This is the single source of truth for AIProof persistence and the CompliLedger
handoff. It maps the :class:`app.schemas.canonical.aiproof.AIProof` model to and
from the persistent :class:`app.models.canonical_aiproof.CanonicalAIProof` row.
"""

from __future__ import annotations

import json
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models._mixins import CANONICAL_SCHEMA_VERSION
from app.models.canonical_aiproof import CanonicalAIProof
from app.repositories.canonical import CanonicalAIProofRepository
from app.schemas.canonical.aiproof import (
    AIProof,
    AIProofStatus,
    CompliLedgerProofHandoff,
    HandoffStatus,
)
from app.services.canonical.aiproof import handoff as handoff_mod
from app.services.canonical.aiproof.handoff import (
    HandoffResult,
    build_handoff_payload,
)
from app.services.canonical.aiproof.verify import (
    AIProofVerification,
    verify_aiproof,
)
from app.utils.timestamps import utc_now


def _proof_to_row(proof: AIProof) -> CanonicalAIProof:
    """Return a :class:`CanonicalAIProof` row for *proof* (new instance)."""
    meta = proof.metadata
    return CanonicalAIProof(
        id=meta.aiproof_id,
        organization_id=meta.organization_id,
        schema_version=CANONICAL_SCHEMA_VERSION,
        proof_schema_version=meta.schema_version,
        proof_type=meta.proof_type,
        governed_outcome=meta.governed_outcome.value,
        status=proof.status.value,
        handoff_status=HandoffStatus.PENDING.value,
        canonicalization_algorithm=proof.canonicalization_algorithm,
        hash_algorithm=proof.hash_algorithm,
        aiproof_hash=proof.aiproof_hash or "",
        signature=proof.signature,
        signer_key_id=proof.signer_key_id,
        issuer=proof.issuer,
        canonical_aiproof=json.dumps(proof.model_dump(mode="json")),
        correlation_id=meta.correlation_id,
        governance_evaluation_id=meta.governance_evaluation_id,
        actor_identity_id=proof.actor_identity.actor_identity_id,
        intent_id=proof.intent.intent_id,
        decision_id=proof.decision.decision_id,
        prior_aiproof_id=proof.prior_aiproof_id,
    )


def _row_to_proof(row: CanonicalAIProof) -> AIProof:
    """Return the :class:`AIProof` model stored in *row*."""
    proof = AIProof.model_validate(json.loads(row.canonical_aiproof))
    # The row status is authoritative for the (mutable) envelope status.
    proof.status = AIProofStatus(row.status)
    return proof


def store_aiproof(db: Session, proof: AIProof) -> CanonicalAIProof:
    """Persist *proof*. Idempotent on the AIProof id."""
    repo = CanonicalAIProofRepository(db)
    existing = repo.get(proof.metadata.organization_id, proof.metadata.aiproof_id)
    if existing is not None:
        existing.status = proof.status.value
        existing.signature = proof.signature
        existing.signer_key_id = proof.signer_key_id
        existing.aiproof_hash = proof.aiproof_hash or ""
        existing.canonical_aiproof = json.dumps(proof.model_dump(mode="json"))
        return repo.save(existing)
    return repo.add(_proof_to_row(proof))


def get_row(
    db: Session, organization_id: str, aiproof_id: str
) -> Optional[CanonicalAIProof]:
    return CanonicalAIProofRepository(db).get(organization_id, aiproof_id)


def get_aiproof(
    db: Session, organization_id: str, aiproof_id: str
) -> Optional[AIProof]:
    row = get_row(db, organization_id, aiproof_id)
    return _row_to_proof(row) if row is not None else None


def list_history(
    db: Session,
    organization_id: str,
    *,
    intent_id: Optional[str] = None,
    actor_identity_id: Optional[str] = None,
    governance_evaluation_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[CanonicalAIProof]:
    return CanonicalAIProofRepository(db).list_by(
        organization_id,
        intent_id=intent_id,
        actor_identity_id=actor_identity_id,
        governance_evaluation_id=governance_evaluation_id,
        correlation_id=correlation_id,
        skip=skip,
        limit=limit,
    )


def verify_local(
    db: Session, organization_id: str, aiproof_id: str
) -> Optional[AIProofVerification]:
    """Independently verify a stored AIProof. Returns ``None`` if unknown."""
    proof = get_aiproof(db, organization_id, aiproof_id)
    if proof is None:
        return None
    return verify_aiproof(proof)


def submit_to_compliledger(
    db: Session,
    organization_id: str,
    aiproof_id: str,
    *,
    requested_proof_policy: Optional[str] = None,
    privacy_classification: Optional[str] = None,
) -> Optional[tuple[CanonicalAIProof, CompliLedgerProofHandoff, HandoffResult]]:
    """Build the handoff payload, submit it, and record the outcome.

    Returns ``None`` when the proof is unknown.
    """
    repo = CanonicalAIProofRepository(db)
    row = repo.get(organization_id, aiproof_id)
    if row is None:
        return None

    proof = _row_to_proof(row)
    payload = build_handoff_payload(
        proof,
        requested_proof_policy=requested_proof_policy,
        privacy_classification=privacy_classification,
    )

    row.status = AIProofStatus.SUBMITTED_TO_COMPLILEDGER.value
    row.handoff_status = HandoffStatus.SUBMITTED.value
    row.requested_proof_policy = payload.requested_proof_policy
    row.privacy_classification = payload.privacy_classification
    row.submitted_at = utc_now()

    result = handoff_mod.get_handoff().submit(payload)

    row.handoff_status = result.status.value
    row.handoff_reference = result.reference
    row.handoff_detail = result.detail
    row.handoff_resolved_at = utc_now()
    if result.status == HandoffStatus.ACCEPTED:
        row.status = AIProofStatus.ACCEPTED_BY_COMPLILEDGER.value
    elif result.status in (HandoffStatus.REJECTED, HandoffStatus.FAILED):
        row.status = AIProofStatus.REJECTED_BY_COMPLILEDGER.value

    repo.save(row)
    return row, payload, result


def get_handoff_status(
    db: Session, organization_id: str, aiproof_id: str
) -> Optional[dict]:
    """Return the handoff status view for a stored AIProof."""
    row = get_row(db, organization_id, aiproof_id)
    if row is None:
        return None
    return {
        "aiproof_id": row.id,
        "status": row.status,
        "handoff_status": row.handoff_status,
        "handoff_reference": row.handoff_reference,
        "handoff_detail": row.handoff_detail,
        "requested_proof_policy": row.requested_proof_policy,
        "privacy_classification": row.privacy_classification,
        "submitted_at": row.submitted_at,
        "handoff_resolved_at": row.handoff_resolved_at,
    }
