"""Audit log routes — read-only access to the append-only event log."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


def build_audit_list_response(logs: list) -> AuditLogListResponse:
    """Convert a list of ORM audit log entries to the list response schema."""
    items = [AuditLogResponse.model_validate(log) for log in logs]
    return AuditLogListResponse(items=items, total=len(items))


@router.get("/", response_model=AuditLogListResponse)
def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Return all audit log entries, newest first."""
    logs = audit_service.list_audit_logs(db, skip=skip, limit=limit)
    return build_audit_list_response(logs)
