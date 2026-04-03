"""Approval Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ApprovalCreate(BaseModel):
    transaction_id: str
    reviewer_id: Optional[str] = None
    action: str  # APPROVE or DENY
    comments: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: str
    transaction_id: str
    reviewer_id: Optional[str] = None
    action: str
    comments: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
