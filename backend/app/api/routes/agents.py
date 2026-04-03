"""Agent CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate
from app.schemas.policy import PolicyResponse
from app.services import agent_service, policy_service
from app.services.policy_service import policy_to_dict

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/", response_model=AgentResponse, status_code=201)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    return agent_service.create_agent(db, payload)


@router.get("/", response_model=list[AgentResponse])
def list_agents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return agent_service.list_agents(db, skip=skip, limit=limit)


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/{agent_id}/policy", response_model=PolicyResponse)
def get_agent_policy(agent_id: str, db: Session = Depends(get_db)):
    """Return the active policy for the given agent."""
    policy = policy_service.get_policy_for_agent(db, agent_id)
    if not policy:
        raise HTTPException(status_code=404, detail="No active policy found for agent")
    return policy_to_dict(policy)


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: str, payload: AgentUpdate, db: Session = Depends(get_db)):
    agent = agent_service.update_agent(db, agent_id, payload)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    if not agent_service.delete_agent(db, agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"detail": "Agent deleted"}
