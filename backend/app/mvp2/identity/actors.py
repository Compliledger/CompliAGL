"""Actor helpers for MVP 2 identity sub-module.

Provides lightweight factory and look-up utilities for actor
representations.  In a production deployment these would talk to a
persistent store; here they demonstrate the interface contract.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.mvp2.schemas.actor import ActorCreate, ActorRead, ActorType


def create_actor(payload: ActorCreate) -> ActorRead:
    """Create a new actor record (in-memory placeholder)."""
    return ActorRead(
        id=uuid4(),
        name=payload.name,
        actor_type=payload.actor_type,
        wallet_address=payload.wallet_address,
        metadata=payload.metadata,
    )


def build_actor(
    name: str,
    actor_type: ActorType = ActorType.AGENT,
    wallet_address: str | None = None,
    actor_id: UUID | None = None,
) -> ActorRead:
    """Build an ``ActorRead`` from individual fields."""
    return ActorRead(
        id=actor_id or uuid4(),
        name=name,
        actor_type=actor_type,
        wallet_address=wallet_address,
    )
