"""EvidenceValidationResult ORM model.

Every :class:`~app.models.raw_evidence.RawEvidence` item receives exactly one
**EvidenceValidationResult**. Validation evaluates a fixed battery of checks —
schema validity, authenticity, integrity, issuer trust, signature validity
(when applicable), subject binding, target binding, transaction/intent binding,
freshness, expiration, revocation, replay risk and source authority — and
collapses them into a single deterministic ``outcome`` drawn from
:class:`~app.utils.canonical_enums.EvidenceValidationOutcome`.
"""

from __future__ import annotations

from sqlalchemy import Column, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class EvidenceValidationResult(CanonicalMixin, Base):
    """The validation verdict for one raw evidence item."""

    __tablename__ = "evidence_validation_results"

    raw_evidence_id = Column(String, nullable=False, index=True)
    evidence_requirement_id = Column(String, nullable=False, index=True)
    collection_job_id = Column(String, nullable=True, index=True)
    policy_resolution_id = Column(String, nullable=True, index=True)

    outcome = Column(String, nullable=False, index=True)
    # Per-check results as a JSON object (check name -> True/False/None).
    checks = Column(Text, nullable=False, default="{}")
    reason_codes = Column(Text, nullable=False, default="[]")
    result_hash = Column(String, nullable=True, index=True)
