"""CRUD service for Agent entities."""

import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentUpdate


def create_agent(db: Session, payload: AgentCreate) -> Agent:
    data = payload.model_dump(exclude={"metadata_json"})
    if payload.metadata_json is not None:
        data["metadata_json"] = json.dumps(payload.metadata_json)
    agent = Agent(**data)
    db.add(agent)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(agent)
    return agent


def get_agent(db: Session, agent_id: str) -> Agent | None:
    return db.query(Agent).filter(Agent.id == agent_id).first()


def get_agent_by_wallet(db: Session, wallet_address: str) -> Agent | None:
    return db.query(Agent).filter(Agent.wallet_address == wallet_address).first()


def list_agents(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
) -> tuple[list[Agent], int]:
    query = db.query(Agent)
    if active_only:
        query = query.filter(Agent.is_active.is_(True))
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return items, total


def update_agent(db: Session, agent_id: str, payload: AgentUpdate) -> Agent | None:
    agent = get_agent(db, agent_id)
    if not agent:
        return None
    update_data = payload.model_dump(exclude_unset=True)
    if "metadata_json" in update_data and update_data["metadata_json"] is not None:
        update_data["metadata_json"] = json.dumps(update_data["metadata_json"])
    for key, value in update_data.items():
        setattr(agent, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(agent)
    return agent


def deactivate_agent(db: Session, agent_id: str) -> Agent | None:
    agent = get_agent(db, agent_id)
    if not agent:
        return None
    agent.is_active = False
    db.commit()
    db.refresh(agent)
    return agent
