"""Audit log Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditLogCreate(BaseModel):
    entity_type: str
    entity_id: str
    action: str
    details: Optional[str] = None
    performed_by: Optional[str] = None


class AuditLogResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    details: Optional[str] = None
    performed_by: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
