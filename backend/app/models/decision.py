"""Decision ORM model — canonical first-class resource.

A **Decision** is the deterministic verdict produced from a governance
evaluation: exactly one of ``APPROVED``, ``DENIED`` or ``ESCALATED``. It is
persisted separately from the evaluation so the decision is an immutable,
independently referenceable record.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import DecisionSupersessionStatus


class Decision(CanonicalMixin, Base):
    """Persistent deterministic governance decision."""

    __tablename__ = "decisions"

    governance_evaluation_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)

    outcome = Column(String, nullable=False)
    reason_codes = Column(Text, nullable=False, default="[]")
    policy_version = Column(String, nullable=True)

    # --- Canonical decision linkage (deterministic engine) ---
    # ``evaluation_id`` is the policy-resolution / evaluation the decision was
    # derived from; ``assessment_id`` binds the factual Assessment the decision
    # maps into a business outcome.
    evaluation_id = Column(String, nullable=True, index=True)
    policy_resolution_id = Column(String, nullable=True, index=True)
    assessment_id = Column(String, nullable=True, index=True)

    # --- Provenance references (JSON text) ---
    # Explicit decision conditions from the governance package that evaluated to
    # true and drove the outcome.
    decision_conditions_triggered = Column(Text, nullable=False, default="[]")
    # The applicable governance packages (id + version + hash) considered.
    applicable_package_ids = Column(Text, nullable=False, default="[]")
    # The applicable requirement ids and the control-evaluation ids aggregated
    # into the assessment this decision consumed.
    applicable_requirement_ids = Column(Text, nullable=False, default="[]")
    control_evaluation_ids = Column(Text, nullable=False, default="[]")

    # --- Bound evidence + input hashes ---
    evidence_package_id = Column(String, nullable=True, index=True)
    evidence_package_hash = Column(String, nullable=True)
    assessment_hash = Column(String, nullable=True)
    policy_package_hash = Column(String, nullable=True)
    actor_hash = Column(String, nullable=True)
    intent_hash = Column(String, nullable=True)
    target_hash = Column(String, nullable=True)
    context_hash = Column(String, nullable=True)

    # --- Determinism / provenance ---
    engine_version = Column(String, nullable=True)
    input_hash = Column(String, nullable=True, index=True)
    decision_hash = Column(String, nullable=True, index=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # --- Immutability / supersession ---
    prior_decision_id = Column(String, nullable=True, index=True)
    superseded_by_decision_id = Column(String, nullable=True, index=True)
    supersession_status = Column(
        String, nullable=False, default=DecisionSupersessionStatus.CURRENT.value
    )
