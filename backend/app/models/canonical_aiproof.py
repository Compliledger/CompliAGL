"""Persistent canonical AIProof ORM model.

This is the **single** persistent proof record for CompliAGL. The full canonical
AIProof (all governance-lifecycle projections) is stored as canonical JSON in
``canonical_aiproof`` together with the fields needed to index, look up,
verify and hand off the proof without re-parsing the whole document.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.schemas.canonical.aiproof import AIProofStatus, HandoffStatus


class CanonicalAIProof(CanonicalMixin, Base):
    """Persistent, canonical AIProof record.

    ``id`` (from :class:`CanonicalMixin`) holds the AIProof id. The immutable
    proof content lives in ``canonical_aiproof`` (canonical JSON); the columns
    below are indexed projections for lookup, history and handoff.
    """

    __tablename__ = "canonical_ai_proofs"

    # Published AIProof schema version (string), distinct from the integer
    # CanonicalMixin.schema_version used for ORM storage evolution.
    proof_schema_version = Column(String, nullable=False)
    proof_type = Column(String, nullable=False)
    governed_outcome = Column(String, nullable=False, index=True)

    # Envelope status + handoff status.
    status = Column(
        String, nullable=False, default=AIProofStatus.GENERATED.value, index=True
    )
    handoff_status = Column(
        String, nullable=False, default=HandoffStatus.PENDING.value, index=True
    )

    # Canonicalization + hashing self-description.
    canonicalization_algorithm = Column(String, nullable=False)
    hash_algorithm = Column(String, nullable=False)

    # Proof binding + signature.
    aiproof_hash = Column(String, nullable=False, index=True)
    signature = Column(Text, nullable=True)
    signer_key_id = Column(String, nullable=False)
    issuer = Column(String, nullable=False)

    # The full canonical AIProof document (canonical JSON).
    canonical_aiproof = Column(Text, nullable=False)

    # Indexed lifecycle references for history / correlation lookups.
    correlation_id = Column(String, nullable=True, index=True)
    governance_evaluation_id = Column(String, nullable=True, index=True)
    actor_identity_id = Column(String, nullable=True, index=True)
    intent_id = Column(String, nullable=True, index=True)
    decision_id = Column(String, nullable=True, index=True)
    prior_aiproof_id = Column(String, nullable=True, index=True)

    # Handoff metadata.
    requested_proof_policy = Column(String, nullable=True)
    privacy_classification = Column(String, nullable=True)
    handoff_reference = Column(String, nullable=True)
    handoff_detail = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    handoff_resolved_at = Column(DateTime(timezone=True), nullable=True)
