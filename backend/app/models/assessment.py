"""Assessment ORM model — canonical first-class resource.

An **Assessment** is the persistent aggregation of the control evaluations for
one evaluation. The *Assessment* runtime stage runs **after** Control
Evaluation and **before** the Decision stage.

Assessment is deliberately **factual**: it aggregates the control evaluations
and the evidence-sufficiency result into one of ``SATISFIED``,
``NOT_SATISFIED``, ``NOT_EVALUABLE`` or ``MANUAL_REVIEW_REQUIRED`` **without**
producing the final business decision. Mapping the assessment (together with
explicit decision conditions) into ``APPROVED`` / ``DENIED`` / ``ESCALATED`` is
the separate Decision stage — Assessment never emits those outcomes.

The record captures the aggregated control-evaluation ids, a mandatory-control
summary, the evidence-sufficiency result, the overall assessment result, reason
codes, and deterministic ``input_hash`` / ``assessment_hash`` values so the
assessment can be replayed and audited.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class Assessment(CanonicalMixin, Base):
    """Persistent, factual aggregation of control evaluations."""

    __tablename__ = "assessments"

    # --- Linkage to the preceding stages ---
    evaluation_id = Column(String, nullable=False, index=True)
    policy_resolution_id = Column(String, nullable=False, index=True)
    applicable_control_set_id = Column(String, nullable=True, index=True)
    evidence_sufficiency_id = Column(String, nullable=True, index=True)

    # --- Aggregation output ---
    control_evaluation_ids = Column(Text, nullable=False, default="[]")
    mandatory_control_summary = Column(Text, nullable=False, default="{}")
    evidence_sufficiency_result = Column(String, nullable=True)
    overall_result = Column(String, nullable=False)
    reason_codes = Column(Text, nullable=False, default="[]")

    # --- Determinism / provenance ---
    engine_version = Column(String, nullable=False)
    input_hash = Column(String, nullable=True, index=True)
    assessment_hash = Column(String, nullable=True, index=True)
    assessed_at = Column(DateTime(timezone=True), nullable=True)
