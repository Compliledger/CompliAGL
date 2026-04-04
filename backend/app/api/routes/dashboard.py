"""Dashboard routes — aggregate and per-agent summaries."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.dashboard import (
    AgentDashboardSummaryResponse,
    DashboardSummaryResponse,
)
from app.services.dashboard_service import get_agent_summary, get_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(db: Session = Depends(get_db)):
    """Return platform-wide aggregate statistics."""
    return get_dashboard_summary(db)


@router.get(
    "/agent/{agent_id}/summary",
    response_model=AgentDashboardSummaryResponse,
)
def agent_dashboard_summary(agent_id: str, db: Session = Depends(get_db)):
    """Return dashboard data scoped to a single agent."""
    result = get_agent_summary(db, agent_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result
