"""ResolutionEvidence ORM model — canonical first-class resource.

**ResolutionEvidence** is the evidence submitted to prove a :class:`Finding` has
actually been remediated. It reuses the same evidence architecture as the
governance evidence layer (orchestration, validation, normalization and
sufficiency): each item receives a deterministic validation outcome and, when
valid, normalized claims, and the collection of items for a finding is evaluated
for sufficiency against the plan's ``required_resolution_evidence``.

Submitting or "completing" remediation is never proof of resolution — only
*validated* resolution evidence can drive a re-assessment.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import (
    EvidenceCollectionStatus,
    SensitivityClassification,
)


class ResolutionEvidence(CanonicalMixin, Base):
    """A single resolution-evidence item submitted against a finding."""

    __tablename__ = "resolution_evidence"

    # --- Linkage ---
    finding_id = Column(String, nullable=False, index=True)
    remediation_plan_id = Column(String, nullable=True, index=True)
    # The required-resolution-evidence descriptor this item satisfies.
    evidence_type = Column(String, nullable=False, index=True)

    # --- Source / bindings (mirrors RawEvidence provenance anchors) ---
    source_id = Column(String, nullable=True, index=True)
    source_type = Column(String, nullable=True, index=True)
    subject_id = Column(String, nullable=True, index=True)
    target_id = Column(String, nullable=True, index=True)
    intent_id = Column(String, nullable=True, index=True)

    # --- Temporal fields ---
    collected_at = Column(DateTime(timezone=True), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # --- Payload / claims ---
    payload = Column(Text, nullable=True)
    payload_reference = Column(String, nullable=True)
    payload_hash = Column(String, nullable=True, index=True)
    claims = Column(Text, nullable=True)

    # --- Classification / provenance ---
    sensitivity = Column(
        String, nullable=False, default=SensitivityClassification.INTERNAL.value
    )
    issuer = Column(String, nullable=True)
    signature = Column(Text, nullable=True)
    provenance = Column(Text, nullable=False, default="{}")
    collection_status = Column(
        String, nullable=False, default=EvidenceCollectionStatus.COLLECTED.value
    )

    # --- Deterministic validation + normalization output ---
    validation_outcome = Column(String, nullable=True, index=True)
    validation_checks = Column(Text, nullable=False, default="{}")
    normalized_claims = Column(Text, nullable=True)
    reason_codes = Column(Text, nullable=False, default="[]")

    # Where the item was submitted from (e.g. DEVSYNC, API, REVIEW).
    submitted_via = Column(String, nullable=True)

    # --- Determinism / provenance ---
    result_hash = Column(String, nullable=True, index=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
