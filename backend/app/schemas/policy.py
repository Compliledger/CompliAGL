"""Policy Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    policy_type: str
    parameters: dict[str, Any] = {}
    is_active: bool = True


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    policy_type: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    policy_type: str
    parameters: dict[str, Any] = {}
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
