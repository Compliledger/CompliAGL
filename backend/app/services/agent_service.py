"""CRUD service for Agent entities."""

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentUpdate


def create_agent(db: Session, payload: AgentCreate) -> Agent:
    agent = Agent(**payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_agent(db: Session, agent_id: str) -> Agent | None:
    return db.query(Agent).filter(Agent.id == agent_id).first()


def list_agents(db: Session, skip: int = 0, limit: int = 100) -> list[Agent]:
    return db.query(Agent).offset(skip).limit(limit).all()


def update_agent(db: Session, agent_id: str, payload: AgentUpdate) -> Agent | None:
    agent = get_agent(db, agent_id)
    if not agent:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(db: Session, agent_id: str) -> bool:
    agent = get_agent(db, agent_id)
    if not agent:
        return False
    db.delete(agent)
    db.commit()
    return True
