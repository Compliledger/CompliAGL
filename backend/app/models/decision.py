"""Decision ORM model — canonical first-class resource.

A **Decision** is the deterministic verdict produced from a governance
evaluation: exactly one of ``APPROVED``, ``DENIED`` or ``ESCALATED``. It is
persisted separately from the evaluation so the decision is an immutable,
independently referenceable record.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class Decision(CanonicalMixin, Base):
    """Persistent deterministic governance decision."""

    __tablename__ = "decisions"

    governance_evaluation_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)

    outcome = Column(String, nullable=False)
    reason_codes = Column(Text, nullable=False, default="[]")
    policy_version = Column(String, nullable=True)

    decision_hash = Column(String, nullable=True, index=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
