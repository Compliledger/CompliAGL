"""Policy schemas for MVP 2."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyStatus(str, Enum):
    """Activation status of a governance policy."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class PolicyBase(BaseModel):
    """Shared fields for policy representations."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    policy_type: str = Field(..., min_length=1, max_length=128)
    rules: dict = Field(default_factory=dict)
    status: PolicyStatus = PolicyStatus.ACTIVE


class PolicyCreate(PolicyBase):
    """Payload for creating a new policy."""


class PolicyRead(PolicyBase):
    """Policy representation returned by the API."""

    id: UUID

    model_config = {"from_attributes": True}
