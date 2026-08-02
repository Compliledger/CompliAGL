"""EvidenceSufficiency ORM model — canonical first-class resource.

An **EvidenceSufficiency** record is the persistent output of the *Evidence
Sufficiency* runtime stage. That stage runs **after** evidence collection /
normalization (which produces the :class:`CanonicalEvidencePackage`) and
**before** formal Control Evaluation.

Evidence Sufficiency evaluates the :class:`CanonicalEvidencePackage` against the
:class:`EvidenceRequirementSet`. Per evidence requirement it produces one of
``SATISFIED``, ``PARTIAL``, ``MISSING``, ``INVALID``, ``STALE``,
``NOT_EVALUABLE`` or ``MANUAL_REVIEW_REQUIRED``. The overall outcome is one of
``SUFFICIENT``, ``PARTIAL``, ``INSUFFICIENT``, ``NOT_EVALUABLE`` or
``MANUAL_REVIEW_REQUIRED`` — and is **never** ``SUFFICIENT`` when any mandatory
evidence requirement is missing, invalid, stale, expired, revoked or not
evaluable.

The per-requirement results are stored as a JSON list
(``requirement_results``); each entry carries its own deterministic
``sufficiency_hash``. The record as a whole is bound by deterministic
``input_hash`` / ``result_hash`` values so identical inputs reproduce identical
results.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class EvidenceSufficiency(CanonicalMixin, Base):
    """Persistent evidence-sufficiency verdict for one evaluation."""

    __tablename__ = "evidence_sufficiency_results"

    # --- Linkage to the preceding stages ---
    evaluation_id = Column(String, nullable=False, index=True)
    policy_resolution_id = Column(String, nullable=False, index=True)
    evidence_requirement_set_id = Column(String, nullable=True, index=True)
    canonical_evidence_package_id = Column(String, nullable=True, index=True)
    collection_job_id = Column(String, nullable=True, index=True)

    # --- Sufficiency output ---
    # JSON list of per-requirement sufficiency entries. Each entry includes the
    # evidence_requirement_id, resolved state, mandatory flag, cardinality,
    # satisfied count, the underlying validation outcomes, the per-requirement
    # status, reason codes and a deterministic sufficiency hash.
    requirement_results = Column(Text, nullable=False, default="[]")
    overall_result = Column(String, nullable=False)
    reason_codes = Column(Text, nullable=False, default="[]")

    # --- Determinism / provenance ---
    engine_version = Column(String, nullable=False)
    input_hash = Column(String, nullable=True, index=True)
    result_hash = Column(String, nullable=True, index=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
