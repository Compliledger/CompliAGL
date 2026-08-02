"""ApplicabilityEvaluation ORM model — canonical first-class resource.

An **ApplicabilityEvaluation** is the persistent output of the *Applicability
Evaluation* runtime stage. That stage runs **after** Policy Resolution and
**separately from** the decision engine. It evaluates each candidate
requirement independently, using only the restricted deterministic expression
engine, and records exactly one of ``APPLICABLE``, ``NOT_APPLICABLE``,
``CONDITIONAL`` or ``INDETERMINATE`` per requirement.

``INDETERMINATE`` is a first-class result and is never silently treated as
``NOT_APPLICABLE``: missing context surfaces explicitly so it cannot silently
produce approval.

Each record captures the full factual basis required for audit and
deterministic replay: the governing package id + version, the requirement id +
version, the actor/intent/target/context ids, the evaluated expression, the
relevant observed values, reason codes, the deterministic engine version, and
deterministic ``input_hash`` / ``result_hash`` values.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class ApplicabilityEvaluation(CanonicalMixin, Base):
    """Persistent, per-requirement deterministic applicability result."""

    __tablename__ = "applicability_evaluations"

    # --- Linkage to the resolution stage ---
    policy_resolution_id = Column(String, nullable=False, index=True)

    # --- Runtime inputs ---
    actor_identity_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=True, index=True)
    operational_context_id = Column(String, nullable=True, index=True)

    # --- Exact governing package + requirement versions ---
    package_id = Column(String, nullable=False, index=True)
    package_version = Column(String, nullable=False)
    requirement_id = Column(String, nullable=False, index=True)
    requirement_version = Column(String, nullable=True)

    # --- Result ---
    result = Column(String, nullable=False)
    # Canonical JSON of the deterministic expression that was evaluated.
    evaluated_expression = Column(Text, nullable=True)
    # Relevant observed values / factual basis + input references (JSON text).
    observed_values = Column(Text, nullable=False, default="[]")
    reason_codes = Column(Text, nullable=False, default="[]")

    # --- Determinism / provenance ---
    engine_version = Column(String, nullable=False)
    input_hash = Column(String, nullable=True, index=True)
    result_hash = Column(String, nullable=True, index=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
