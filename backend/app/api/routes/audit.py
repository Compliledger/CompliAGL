"""Audit log routes — read-only access to the event log."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.audit import AuditLogResponse
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/", response_model=list[AuditLogResponse])
def list_audit_logs(
    entity_type: str | None = None,
    entity_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return audit_service.list_audit_logs(db, entity_type=entity_type, entity_id=entity_id, skip=skip, limit=limit)


@router.get("/{log_id}", response_model=AuditLogResponse)
def get_audit_log(log_id: str, db: Session = Depends(get_db)):
    log = audit_service.get_audit_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log entry not found")
    return log
