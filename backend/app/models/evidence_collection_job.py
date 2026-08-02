"""EvidenceCollectionJob ORM model.

An **EvidenceCollectionJob** is the record of executing an
:class:`~app.models.evidence_orchestration_plan.EvidenceOrchestrationPlan`. It
tracks the aggregate collection status, the raw evidence produced, the explicit
collection failures, and the requirements that remain unresolved. It is the
persistent, inspectable status surface for the *start collection* / *inspect
status* APIs.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import EvidenceCollectionStatus


class EvidenceCollectionJob(CanonicalMixin, Base):
    """Execution record for an evidence orchestration plan."""

    __tablename__ = "evidence_collection_jobs"

    policy_resolution_id = Column(String, nullable=False, index=True)
    evidence_requirement_set_id = Column(String, nullable=False, index=True)
    orchestration_plan_id = Column(String, nullable=False, index=True)

    production_mode = Column(Boolean, nullable=False, default=False)
    status = Column(
        String, nullable=False, default=EvidenceCollectionStatus.PENDING.value
    )

    # JSON lists of ids / structured records produced by the run.
    raw_evidence_ids = Column(Text, nullable=False, default="[]")
    failures = Column(Text, nullable=False, default="[]")
    unresolved = Column(Text, nullable=False, default="[]")
    reason_codes = Column(Text, nullable=False, default="[]")

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
