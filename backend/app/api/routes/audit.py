"""Audit log routes — read-only access to the append-only event log."""

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import model_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


class _AuditLogOut(AuditLogResponse):
    """Internal schema that deserialises the JSON text stored in event_data."""

    @model_validator(mode="before")
    @classmethod
    def _parse_event_data(cls, data: Any) -> Any:
        # Handle ORM objects (have __dict__) and plain dicts
        if hasattr(data, "__dict__"):
            raw = getattr(data, "event_data", None)
        else:
            raw = data.get("event_data") if isinstance(data, dict) else None
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if hasattr(data, "__dict__"):
                object.__setattr__(data, "event_data", parsed)
            else:
                data["event_data"] = parsed
        return data


def _to_response(logs: list) -> AuditLogListResponse:
    """Convert a list of ORM audit log entries to the list response schema."""
    items = [_AuditLogOut.model_validate(log) for log in logs]
    return AuditLogListResponse(items=items, total=len(items))


@router.get("/", response_model=AuditLogListResponse)
def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Return all audit log entries, newest first."""
    logs = audit_service.list_audit_logs(db, skip=skip, limit=limit)
    return _to_response(logs)
