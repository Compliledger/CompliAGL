"""EvidenceRequirementSet ORM model — canonical first-class resource.

An **EvidenceRequirementSet** is the persistent output of the *Evidence
Requirement Resolution* runtime stage. That stage runs **after** Control
Determination and **before** evidence collection.

Evidence Requirement Resolution consumes the :class:`ApplicableControlSet` for
a resolution and:

1. resolves the evidence needed by every applicable control,
2. deduplicates evidence requirements shared across controls,
3. preserves the mappings between evidence requirements, controls and
   requirements,
4. defines, for each evidence requirement, the required evidence type, subject,
   target, allowed source type, allowed issuer, freshness threshold,
   validation method, cardinality and mandatory status,
5. assigns each evidence requirement a deterministic state — ``REQUIRED``,
   ``OPTIONAL``, ``CONDITIONAL``, ``NOT_REQUIRED`` or ``UNRESOLVED``.

``UNRESOLVED`` is produced when the applicability basis for the controls that
need an evidence item is missing or indeterminate, so a missing basis can never
silently produce success.

The evidence requirements are stored as a JSON list (``evidence_requirements``);
each entry carries its own deterministic ``resolution_hash``. The set as a whole
is bound by deterministic ``input_hash`` / ``result_hash`` values.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class EvidenceRequirementSet(CanonicalMixin, Base):
    """Persistent set of evidence requirements resolved for a resolution."""

    __tablename__ = "evidence_requirement_sets"

    # --- Linkage to the preceding stages ---
    policy_resolution_id = Column(String, nullable=False, index=True)
    applicable_control_set_id = Column(String, nullable=False, index=True)

    # --- Runtime inputs (carried for traceability / replay) ---
    actor_identity_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=True, index=True)
    operational_context_id = Column(String, nullable=True, index=True)

    # --- Resolution output ---
    # JSON list of resolved evidence requirement entries. Each entry includes
    # the evidence_requirement_id, the controls + requirements it is traceable
    # to, the governing package ids + versions, the required evidence type,
    # subject, target, allowed source type, allowed issuers, freshness
    # threshold, validation method, cardinality, mandatory status, the resolved
    # state and a deterministic resolution hash.
    evidence_requirements = Column(Text, nullable=False, default="[]")
    reason_codes = Column(Text, nullable=False, default="[]")

    # --- Determinism / provenance ---
    engine_version = Column(String, nullable=False)
    input_hash = Column(String, nullable=True, index=True)
    result_hash = Column(String, nullable=True, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
