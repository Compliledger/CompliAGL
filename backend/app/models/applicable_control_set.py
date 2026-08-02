"""ApplicableControlSet ORM model — canonical first-class resource.

An **ApplicableControlSet** is the persistent output of the *Control
Determination* runtime stage. That stage runs **after** Applicability
Evaluation and **before** evidence collection and the decision engine.

Control Determination consumes the per-requirement
:class:`ApplicabilityEvaluation` results for a policy resolution and:

1. selects the controls mapped to ``APPLICABLE`` or conditionally applicable
   requirements,
2. excludes controls whose requirements are all ``NOT_APPLICABLE``,
3. preserves ``CONDITIONAL`` and ``INDETERMINATE`` status (a missing
   applicability basis surfaces as ``INDETERMINATE``, never silently
   ``NOT_APPLICABLE``),
4. deduplicates controls shared across requirements,
5. resolves each control's priority and mandatory status,
6. records the exact governing package ids + versions and the requirement ids
   each control is traceable to.

The controls themselves are stored as a JSON list (``controls``); each entry
carries its own deterministic ``determination_hash``. The set as a whole is
bound by deterministic ``input_hash`` / ``result_hash`` values so identical
inputs and package versions reproduce identical results.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class ApplicableControlSet(CanonicalMixin, Base):
    """Persistent set of controls determined applicable for a resolution."""

    __tablename__ = "applicable_control_sets"

    # --- Linkage to the preceding stages ---
    policy_resolution_id = Column(String, nullable=False, index=True)

    # --- Runtime inputs (carried for traceability / replay) ---
    actor_identity_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=True, index=True)
    operational_context_id = Column(String, nullable=True, index=True)

    # --- Determination output ---
    # JSON list of applicable control entries. Each entry includes the
    # applicable_control_id, control_id, requirement ids, governance package
    # ids + versions, control objective, mandatory flag, severity, evaluation
    # expression, expected outcome, failure disposition, remediation
    # eligibility, evidence requirement ids, status, determination reason and
    # determination hash.
    controls = Column(Text, nullable=False, default="[]")
    reason_codes = Column(Text, nullable=False, default="[]")

    # --- Determinism / provenance ---
    engine_version = Column(String, nullable=False)
    input_hash = Column(String, nullable=True, index=True)
    result_hash = Column(String, nullable=True, index=True)
    determined_at = Column(DateTime(timezone=True), nullable=True)
