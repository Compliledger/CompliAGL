"""Audit log Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    agent_id: str
    transaction_id: Optional[str] = None
    event_type: str
    event_summary: str
    event_data: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
