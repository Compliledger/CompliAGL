"""Actor schemas for MVP 2."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ActorType(str, Enum):
    """Classification of an actor in the governance system."""

    AGENT = "AGENT"
    HUMAN = "HUMAN"
    ORGANIZATION = "ORGANIZATION"


class ActorBase(BaseModel):
    """Shared fields for actor representations."""

    name: str = Field(..., min_length=1, max_length=255)
    actor_type: ActorType
    wallet_address: str | None = None
    metadata: dict | None = None


class ActorCreate(ActorBase):
    """Payload for creating a new actor."""


class ActorRead(ActorBase):
    """Actor representation returned by the API."""

    id: UUID

    model_config = {"from_attributes": True}
