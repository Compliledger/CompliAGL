"""In-memory actor registry for CompliAGL MVP 2."""

from __future__ import annotations

from app.mvp2.schemas.actor import ActorIdentity, ActorType

_ACTOR_REGISTRY: dict[str, ActorIdentity] = {}


def seed_demo_actors() -> None:
    """Populate the registry with default demo actors."""
    demo_actors = [
        ActorIdentity(
            actor_id="actor-1",
            actor_type=ActorType.AI_AGENT,
            name="TravelAgent-01",
            wallet_address="agent_wallet_travel_001",
            did="did:compliagl:travelagent01",
        ),
        ActorIdentity(
            actor_id="human-1",
            actor_type=ActorType.HUMAN,
            name="OpsManager-01",
            wallet_address="human_wallet_ops_001",
            did="did:compliagl:opsmanager01",
        ),
    ]
    for actor in demo_actors:
        _ACTOR_REGISTRY[actor.actor_id] = actor


def get_actor(actor_id: str) -> ActorIdentity | None:
    """Return an actor by *actor_id*, or ``None`` if not found."""
    return _ACTOR_REGISTRY.get(actor_id)


def list_actors() -> list[ActorIdentity]:
    """Return all registered actors."""
    return list(_ACTOR_REGISTRY.values())
