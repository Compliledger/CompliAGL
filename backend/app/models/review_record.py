"""ReviewRecord ORM model — canonical first-class resource.

A **ReviewRecord** captures a required human review with an explicit reviewer
identity. It backs two governance rules:

* Manual review must produce a review record and reviewer identity.
* Manager approval can resolve an escalation.

A review record is evidence of *who* decided *what* and *why*; it never bypasses
the deterministic pipeline — a resolved review still flows into resolution
validation and a new deterministic decision.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import ReviewType


class ReviewRecord(CanonicalMixin, Base):
    """A human review of a finding / escalation with reviewer identity."""

    __tablename__ = "review_records"

    finding_id = Column(String, nullable=True, index=True)
    decision_id = Column(String, nullable=True, index=True)
    intent_id = Column(String, nullable=True, index=True)

    review_type = Column(
        String, nullable=False, default=ReviewType.MANUAL_REVIEW.value
    )
    # The reviewer identity is mandatory — a manual review can never be
    # anonymous.
    reviewer_id = Column(String, nullable=False, index=True)
    reviewer_role = Column(String, nullable=True)

    outcome = Column(String, nullable=False)
    rationale = Column(Text, nullable=True)

    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_hash = Column(String, nullable=True, index=True)
