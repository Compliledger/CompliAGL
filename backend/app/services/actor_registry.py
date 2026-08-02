"""Canonical persistent actor registry.

This is the single, persistent source of truth for actors. It is backed by the
``agents`` table (the :class:`app.models.agent.Agent` ORM model) and replaces
the deprecated in-memory registry in ``app/mvp2/identity/actors.py``.

An *actor* in the canonical CompliAGL boundary is any entity that submits an
intent — an autonomous agent, a human operator, or an organization. All three
are stored in the ``agents`` table and distinguished by ``actor_type``.
"""

from __future__ import annotations

import json
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.mvp2.schemas.actor import ActorCreate, ActorRead, ActorType


def _to_actor_read(agent: Agent) -> ActorRead:
    """Map an :class:`Agent` ORM row to the :class:`ActorRead` domain model."""
    metadata = None
    if agent.metadata_json:
        try:
            metadata = json.loads(agent.metadata_json)
        except (ValueError, TypeError):
            metadata = None
    try:
        actor_type = ActorType(agent.actor_type)
    except ValueError:
        actor_type = ActorType.AGENT
    return ActorRead(
        id=UUID(str(agent.id)),
        name=agent.name,
        actor_type=actor_type,
        wallet_address=agent.wallet_address,
        metadata=metadata,
    )


def get_actor(db: Session, actor_id: UUID) -> ActorRead | None:
    """Return an actor by id, or ``None`` if not found."""
    agent = db.get(Agent, str(actor_id))
    return _to_actor_read(agent) if agent is not None else None


def list_actors(db: Session) -> list[ActorRead]:
    """Return every registered actor."""
    agents = db.execute(select(Agent)).scalars().all()
    return [_to_actor_read(agent) for agent in agents]


def create_actor(db: Session, payload: ActorCreate) -> ActorRead:
    """Create and persist a new actor."""
    agent = Agent(
        id=str(uuid.uuid4()),
        name=payload.name,
        actor_type=payload.actor_type.value,
        wallet_address=payload.wallet_address
        or f"wallet_{uuid.uuid4().hex[:16]}",
        metadata_json=json.dumps(payload.metadata) if payload.metadata else None,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _to_actor_read(agent)


def upsert_actor(
    db: Session,
    *,
    actor_id: UUID,
    name: str,
    actor_type: ActorType,
    wallet_address: str,
) -> ActorRead:
    """Idempotently create or update an actor with a fixed id (used for seeds)."""
    agent = db.get(Agent, str(actor_id))
    if agent is None:
        agent = Agent(id=str(actor_id))
        db.add(agent)
    agent.name = name
    agent.actor_type = actor_type.value
    agent.wallet_address = wallet_address
    db.commit()
    db.refresh(agent)
    return _to_actor_read(agent)
