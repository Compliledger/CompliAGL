"""Agent CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate
from app.schemas.audit import AuditLogListResponse
from app.services import agent_service, audit_service
from app.api.routes.audit import build_audit_list_response

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


@router.get("/{agent_id}/audit", response_model=AuditLogListResponse, tags=["audit"])
def list_agent_audit_logs(
    agent_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Return audit log entries for a specific agent, newest first."""
    logs = audit_service.list_audit_logs_for_agent(db, agent_id, skip=skip, limit=limit)
    return build_audit_list_response(logs)
