"""Finding ORM model — canonical first-class persistent domain object.

A **Finding** is created on the finding-and-remediation branch. That branch
applies when an assessment or decision is ``NOT_SATISFIED``, ``NOT_EVALUABLE``,
``MANUAL_REVIEW_REQUIRED``, ``DENIED`` or ``ESCALATED`` (subject to
governance-package configuration). Not every denial is remediable: a terminal
policy prohibition produces a finding that is ``INELIGIBLE`` for remediation and
terminal.

A finding is the durable, auditable statement of *what is wrong*, *why the
decision was affected*, and *whether it can be remediated at all*. It links back
to the exact evaluation / assessment / decision / intent that produced it and
carries a deterministic ``finding_hash``.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import (
    FindingStatus,
    RemediationEligibility,
)


class Finding(CanonicalMixin, Base):
    """Persistent governance finding raised from a denial / escalation."""

    __tablename__ = "findings"

    # Stable, human-referenceable identifier (distinct from the surrogate id).
    finding_id = Column(String, nullable=False, index=True)

    # --- Provenance linkage to the deterministic pipeline ---
    evaluation_id = Column(String, nullable=True, index=True)
    assessment_id = Column(String, nullable=True, index=True)
    decision_id = Column(String, nullable=True, index=True)
    intent_id = Column(String, nullable=True, index=True)
    actor_id = Column(String, nullable=True, index=True)
    target_id = Column(String, nullable=True, index=True)

    # --- Traceability references (JSON text) ---
    requirement_ids = Column(Text, nullable=False, default="[]")
    control_ids = Column(Text, nullable=False, default="[]")
    evidence_gap_ids = Column(Text, nullable=False, default="[]")

    # --- Description / classification ---
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String, nullable=False)
    finding_type = Column(String, nullable=False, index=True)
    decision_impact = Column(String, nullable=True)

    # --- Remediation posture ---
    remediation_eligibility = Column(
        String, nullable=False, default=RemediationEligibility.ELIGIBLE.value
    )
    terminal = Column(Boolean, nullable=False, default=False)

    # --- Workflow state ---
    status = Column(String, nullable=False, default=FindingStatus.OPEN.value)
    owner = Column(String, nullable=True, index=True)
    due_date = Column(DateTime(timezone=True), nullable=True)

    # --- Resolution outcome (populated after validated resolution) ---
    resolution_validation_outcome = Column(String, nullable=True)
    resolved_by_decision_id = Column(String, nullable=True, index=True)

    reason_codes = Column(Text, nullable=False, default="[]")

    # Reason codes from the *resolution phase* (resolution validation /
    # re-assessment) — e.g. why a resolution attempt was rejected or a
    # re-assessment was blocked. Kept separate from ``reason_codes`` (the
    # generation-time codes) and deliberately NOT part of ``finding_hash``:
    # this is a post-generation mutation, like ``resolution_validation_outcome``.
    # ``None`` until the resolution phase writes to it.
    resolution_reason_codes = Column(Text, nullable=True)

    # --- Determinism / provenance ---
    finding_hash = Column(String, nullable=True, index=True)
