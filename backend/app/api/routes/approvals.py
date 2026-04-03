"""Approval routes — handle escalation reviews."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.approval import ApprovalCreate, ApprovalResponse
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/", response_model=ApprovalResponse, status_code=201)
def create_approval(payload: ApprovalCreate, db: Session = Depends(get_db)):
    return approval_service.create_approval(db, payload)


@router.get("/", response_model=list[ApprovalResponse])
def list_approvals(transaction_id: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return approval_service.list_approvals(db, transaction_id=transaction_id, skip=skip, limit=limit)


@router.get("/{approval_id}", response_model=ApprovalResponse)
def get_approval(approval_id: str, db: Session = Depends(get_db)):
    approval = approval_service.get_approval(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval
