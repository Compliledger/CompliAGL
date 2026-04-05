"""Actor helpers for MVP 2 identity sub-module.

Provides lightweight factory and look-up utilities for actor
representations.  In a production deployment these would talk to a
persistent store; here they demonstrate the interface contract.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.mvp2.schemas.actor import ActorCreate, ActorRead, ActorType

# ---------------------------------------------------------------------------
# In-memory actor registry (MVP 2)
# ---------------------------------------------------------------------------

_ACTOR_REGISTRY: dict[UUID, ActorRead] = {}


def seed_demo_actors() -> None:
    """Populate the registry with default demo actors.

    Safe to call multiple times — existing entries are overwritten with the
    canonical demo data.
    """
    demo_actors = [
        ActorRead(
            id=uuid4(),
            name="TravelAgent-01",
            actor_type=ActorType.AGENT,
            wallet_address="agent_wallet_travel_001",
        ),
        ActorRead(
            id=uuid4(),
            name="OpsManager-01",
            actor_type=ActorType.HUMAN,
            wallet_address="human_wallet_ops_001",
        ),
    ]
    for actor in demo_actors:
        _ACTOR_REGISTRY[actor.id] = actor


def get_actor(actor_id: UUID) -> ActorRead | None:
    """Return an actor by *actor_id*, or ``None`` if not found."""
    return _ACTOR_REGISTRY.get(actor_id)


def list_actors() -> list[ActorRead]:
    """Return all registered actors."""
    return list(_ACTOR_REGISTRY.values())


def create_actor(payload: ActorCreate) -> ActorRead:
    """Create a new actor record (in-memory placeholder)."""
    actor = ActorRead(
        id=uuid4(),
        name=payload.name,
        actor_type=payload.actor_type,
        wallet_address=payload.wallet_address,
        metadata=payload.metadata,
    )
    _ACTOR_REGISTRY[actor.id] = actor
    return actor


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
