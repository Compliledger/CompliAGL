"""ControlEvaluation ORM model — canonical first-class resource.

A **ControlEvaluation** is the persistent, immutable result of formally
evaluating exactly one :class:`ApplicableControl`. The *Control Evaluation*
runtime stage runs **after** Evidence Sufficiency and **before** Assessment.

Each control is evaluated using:

* **normalized evidence only** (raw intent assertions can never satisfy a
  control),
* the approved deterministic expression engine,
* the exact control version,
* the exact governance package version.

Exactly one ``ControlEvaluation`` row is produced per control per evaluation
run, and it records the full deterministic detail required to reproduce and
audit the verdict — the evaluation expression, expected value, observed value,
result, reason codes, severity, the evidence and evidence-sufficiency
references, the deterministic engine version, and both the input and result
hashes.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class ControlEvaluation(CanonicalMixin, Base):
    """The immutable evaluation result for one applicable control."""

    __tablename__ = "control_evaluations"

    # --- Linkage to the preceding stages ---
    evaluation_id = Column(String, nullable=False, index=True)
    policy_resolution_id = Column(String, nullable=False, index=True)
    applicable_control_set_id = Column(String, nullable=True, index=True)
    evidence_sufficiency_id = Column(String, nullable=True, index=True)
    canonical_evidence_package_id = Column(String, nullable=True, index=True)

    # --- Control identity / version ---
    # Deterministic, content-addressed id for this control's evaluation.
    control_evaluation_id = Column(String, nullable=False, index=True)
    control_id = Column(String, nullable=False, index=True)
    package_id = Column(String, nullable=True, index=True)
    # The exact governance package version and control version used.
    package_version = Column(String, nullable=True)
    control_version = Column(String, nullable=True)
    mandatory = Column(Boolean, nullable=False, default=True)
    severity = Column(String, nullable=True)

    # --- Traceability references (JSON) ---
    requirement_ids = Column(Text, nullable=False, default="[]")
    evidence_requirement_ids = Column(Text, nullable=False, default="[]")
    evidence_references = Column(Text, nullable=False, default="[]")
    evidence_sufficiency_references = Column(Text, nullable=False, default="[]")

    # --- Evaluation detail ---
    evaluation_expression = Column(Text, nullable=True)
    expected_value = Column(Text, nullable=True)
    observed_value = Column(Text, nullable=True)
    result = Column(String, nullable=False)
    reason_codes = Column(Text, nullable=False, default="[]")

    # --- Determinism / provenance ---
    engine_version = Column(String, nullable=False)
    input_hash = Column(String, nullable=True, index=True)
    result_hash = Column(String, nullable=True, index=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
