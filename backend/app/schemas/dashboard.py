"""Dashboard Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.agent import AgentResponse
from app.schemas.audit import AuditLogResponse
from app.schemas.policy import PolicyResponse
from app.schemas.transaction import TransactionResponse


class DashboardSummaryResponse(BaseModel):
    """Aggregate summary across the entire platform."""

    total_agents: int = 0
    active_agents: int = 0
    total_policies: int = 0
    total_transactions: int = 0
    approved_transactions: int = 0
    denied_transactions: int = 0
    escalated_transactions: int = 0
    pending_approvals: int = 0
    executed_transactions: int = 0
    total_volume_submitted: float = 0.0
    total_volume_approved: float = 0.0
    total_volume_executed: float = 0.0


class AgentDashboardSummaryResponse(BaseModel):
    """Per-agent dashboard summary."""

    agent: AgentResponse
    active_policies: list[PolicyResponse] = []
    transactions_today: int = 0
    approved_today: int = 0
    denied_today: int = 0
    escalated_today: int = 0
    spent_today: float = 0.0
    remaining_daily_budget: Optional[float] = None
    recent_transactions: list[TransactionResponse] = []
    recent_audit_events: list[AuditLogResponse] = []
