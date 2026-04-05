"""Actor schemas for CompliAGL MVP 2."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ActorType(str, Enum):
    """Classification of an actor in the governance system."""

    AI_AGENT = "AI_AGENT"
    HUMAN = "HUMAN"
    ORGANIZATION = "ORGANIZATION"


class ActorIdentity(BaseModel):
    """Identity of an actor participating in a governed transaction."""

    actor_id: str
    actor_type: ActorType
    name: str
    wallet_address: str | None = None
    did: str | None = None
