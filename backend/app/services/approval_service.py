"""Approval service — handles escalation reviews."""

import json

from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.transaction import Transaction
from app.schemas.approval import ApprovalCreate
from app.services.audit_service import log_event
from app.utils.enums import ApprovalAction, DecisionStatus


def create_approval(db: Session, payload: ApprovalCreate) -> Approval:
    approval = Approval(**payload.model_dump())
    db.add(approval)

    # Update the related transaction status
    tx = db.query(Transaction).filter(Transaction.id == payload.transaction_id).first()
    if tx:
        if payload.action == ApprovalAction.APPROVE.value:
            tx.status = DecisionStatus.APPROVED.value
        else:
            tx.status = DecisionStatus.DENIED.value

    db.commit()
    db.refresh(approval)

    log_event(
        db,
        entity_type="approval",
        entity_id=approval.id,
        action=payload.action,
        details=json.dumps({"transaction_id": payload.transaction_id, "comments": payload.comments}),
        performed_by=payload.reviewer_id or "unknown",
    )

    return approval


def list_approvals(db: Session, transaction_id: str | None = None, skip: int = 0, limit: int = 100) -> list[Approval]:
    query = db.query(Approval)
    if transaction_id:
        query = query.filter(Approval.transaction_id == transaction_id)
    return query.offset(skip).limit(limit).all()


def get_approval(db: Session, approval_id: str) -> Approval | None:
    return db.query(Approval).filter(Approval.id == approval_id).first()
