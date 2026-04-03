"""Agent Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    wallet_address: Optional[str] = None
    role: Optional[str] = "agent"


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    wallet_address: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    wallet_address: Optional[str] = None
    status: str
    role: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
