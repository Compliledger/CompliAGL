"""Agent Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.utils.enums import ActorType


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    wallet_address: str = Field(..., min_length=1, max_length=255)
    actor_type: ActorType = ActorType.AGENT
    owner_name: Optional[str] = Field(None, max_length=255)
    owner_email: Optional[str] = Field(None, max_length=255)
    metadata_json: Optional[Any] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    wallet_address: Optional[str] = Field(None, min_length=1, max_length=255)
    actor_type: Optional[ActorType] = None
    owner_name: Optional[str] = Field(None, max_length=255)
    owner_email: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    metadata_json: Optional[Any] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    wallet_address: str
    actor_type: ActorType
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    is_active: bool
    metadata_json: Optional[Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    items: list[AgentResponse]
    total: int
