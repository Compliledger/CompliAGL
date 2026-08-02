"""Review service — human review records with reviewer identity.

Backs two governance rules:

* Manual review must produce a review record and a reviewer identity.
* Manager approval can resolve an escalation.

A review record never bypasses the deterministic pipeline. An approving review
is an input to resolution validation, not a substitute for it.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.review_record import ReviewRecord
from app.repositories.canonical import (
    FindingRepository,
    ReviewRecordRepository,
)
from app.schemas.canonical.remediation import ReviewRecordCreate
from app.services.canonical.errors import NotFoundError
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def record(db: Session, payload: ReviewRecordCreate) -> ReviewRecord:
    """Persist a review record with a mandatory reviewer identity."""
    org = payload.organization_id
    finding = FindingRepository(db).get(org, payload.finding_id)
    if finding is None:
        raise NotFoundError(f"Finding not found: {payload.finding_id}")

    now = utc_now()
    review_hash = hash_dict(
        {
            "organization_id": org,
            "finding_id": finding.id,
            "decision_id": finding.decision_id,
            "intent_id": finding.intent_id,
            "review_type": payload.review_type.value,
            "reviewer_id": payload.reviewer_id,
            "outcome": payload.outcome.value,
            "reviewed_at": now.isoformat(),
        }
    )
    obj = ReviewRecord(
        organization_id=org,
        finding_id=finding.id,
        decision_id=finding.decision_id,
        intent_id=finding.intent_id,
        review_type=payload.review_type.value,
        reviewer_id=payload.reviewer_id,
        reviewer_role=payload.reviewer_role,
        outcome=payload.outcome.value,
        rationale=payload.rationale,
        reviewed_at=now,
        review_hash=review_hash,
    )
    return ReviewRecordRepository(db).add(obj)


def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[ReviewRecord]:
    return ReviewRecordRepository(db).get(organization_id, resource_id)


def list_for_finding(
    db: Session, organization_id: str, finding_id: str
) -> Sequence[ReviewRecord]:
    return ReviewRecordRepository(db).list_for_finding(organization_id, finding_id)
