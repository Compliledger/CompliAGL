"""Agent CRUD routes."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.agent import AgentCreate, AgentListResponse, AgentResponse, AgentUpdate
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_to_response(agent) -> dict:
    """Convert an Agent ORM instance to a response-friendly dict."""
    data = {
        "id": agent.id,
        "name": agent.name,
        "wallet_address": agent.wallet_address,
        "actor_type": agent.actor_type,
        "owner_name": agent.owner_name,
        "owner_email": agent.owner_email,
        "is_active": agent.is_active,
        "metadata_json": json.loads(agent.metadata_json) if agent.metadata_json else None,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }
    return data


@router.post("/", response_model=AgentResponse, status_code=201)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    try:
        agent = agent_service.create_agent(db, payload)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"An agent with wallet_address '{payload.wallet_address}' already exists.",
        )
    return _agent_to_response(agent)


@router.get("/", response_model=AgentListResponse)
def list_agents(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    items, total = agent_service.list_agents(db, skip=skip, limit=limit, active_only=active_only)
    return AgentListResponse(
        items=[_agent_to_response(a) for a in items],
        total=total,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return _agent_to_response(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: str, payload: AgentUpdate, db: Session = Depends(get_db)):
    try:
        agent = agent_service.update_agent(db, agent_id, payload)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"An agent with wallet_address '{payload.wallet_address}' already exists.",
        )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return _agent_to_response(agent)


@router.delete("/{agent_id}", response_model=AgentResponse)
def deactivate_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = agent_service.deactivate_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return _agent_to_response(agent)
