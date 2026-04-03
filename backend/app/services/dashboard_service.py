"""Dashboard service — computes summary statistics for the frontend."""

import json
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.audit_log import AuditLog
from app.models.policy import Policy
from app.models.transaction import Transaction


def _today_start_utc() -> datetime:
    """Return midnight UTC for the current day."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _policy_to_dict(policy: Policy) -> dict:
    """Convert a Policy ORM instance to a dict with deserialized parameters."""
    try:
        params = json.loads(policy.parameters) if isinstance(policy.parameters, str) else policy.parameters
    except (json.JSONDecodeError, TypeError):
        params = {}
    return {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "policy_type": policy.policy_type,
        "parameters": params or {},
        "is_active": policy.is_active,
        "created_at": policy.created_at,
        "updated_at": policy.updated_at,
    }


# ---------------------------------------------------------------------------
# Platform-wide summary
# ---------------------------------------------------------------------------


def get_dashboard_summary(db: Session) -> dict:
    """Return aggregate statistics for all agents, policies, and transactions."""

    total_agents = db.query(func.count(Agent.id)).scalar() or 0
    active_agents = (
        db.query(func.count(Agent.id))
        .filter(Agent.status == "ACTIVE")
        .scalar()
        or 0
    )
    total_policies = db.query(func.count(Policy.id)).scalar() or 0
    total_transactions = db.query(func.count(Transaction.id)).scalar() or 0

    approved_transactions = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.status == "APPROVED")
        .scalar()
        or 0
    )
    denied_transactions = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.status == "DENIED")
        .scalar()
        or 0
    )
    escalated_transactions = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.status == "ESCALATED")
        .scalar()
        or 0
    )
    pending_approvals = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.status == "PENDING")
        .scalar()
        or 0
    )
    executed_transactions = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.status == "EXECUTED")
        .scalar()
        or 0
    )

    total_volume_submitted = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0)).scalar()
    )
    total_volume_approved = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
        .filter(Transaction.status == "APPROVED")
        .scalar()
    )
    total_volume_executed = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
        .filter(Transaction.status == "EXECUTED")
        .scalar()
    )

    return {
        "total_agents": total_agents,
        "active_agents": active_agents,
        "total_policies": total_policies,
        "total_transactions": total_transactions,
        "approved_transactions": approved_transactions,
        "denied_transactions": denied_transactions,
        "escalated_transactions": escalated_transactions,
        "pending_approvals": pending_approvals,
        "executed_transactions": executed_transactions,
        "total_volume_submitted": float(total_volume_submitted),
        "total_volume_approved": float(total_volume_approved),
        "total_volume_executed": float(total_volume_executed),
    }


# ---------------------------------------------------------------------------
# Per-agent summary
# ---------------------------------------------------------------------------


def _get_daily_budget(db: Session) -> float | None:
    """Return the daily budget derived from SPEND_LIMIT policies, or None."""
    spend_policies = (
        db.query(Policy)
        .filter(Policy.is_active.is_(True), Policy.policy_type == "SPEND_LIMIT")
        .all()
    )
    if not spend_policies:
        return None

    # Take the minimum spend limit across all active SPEND_LIMIT policies.
    limits: list[float] = []
    for p in spend_policies:
        try:
            params = json.loads(p.parameters) if isinstance(p.parameters, str) else p.parameters
            limit_val = params.get("daily_limit") or params.get("limit")
            if limit_val is not None:
                limits.append(float(limit_val))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    return min(limits) if limits else None


def get_agent_summary(db: Session, agent_id: str) -> dict | None:
    """Return dashboard data scoped to a single agent."""

    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        return None

    today_start = _today_start_utc()

    # Active policies (global — not agent-scoped in this schema)
    active_policies_orm = (
        db.query(Policy).filter(Policy.is_active.is_(True)).all()
    )
    active_policies = [_policy_to_dict(p) for p in active_policies_orm]

    # Today's transactions for this agent
    today_txs = (
        db.query(Transaction)
        .filter(
            Transaction.agent_id == agent_id,
            Transaction.created_at >= today_start,
        )
        .all()
    )

    transactions_today = len(today_txs)
    approved_today = sum(1 for t in today_txs if t.status == "APPROVED")
    denied_today = sum(1 for t in today_txs if t.status == "DENIED")
    escalated_today = sum(1 for t in today_txs if t.status == "ESCALATED")
    spent_today = sum(
        t.amount for t in today_txs if t.status in ("APPROVED", "EXECUTED")
    )

    daily_budget = _get_daily_budget(db)
    remaining_daily_budget = (
        max(daily_budget - spent_today, 0.0)
        if daily_budget is not None
        else None
    )

    # Most recent transactions for this agent (last 10)
    recent_transactions = (
        db.query(Transaction)
        .filter(Transaction.agent_id == agent_id)
        .order_by(Transaction.created_at.desc())
        .limit(10)
        .all()
    )

    # Most recent audit events for this agent (last 10)
    recent_audit_events = (
        db.query(AuditLog)
        .filter(AuditLog.entity_id == agent_id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "agent": agent,
        "active_policies": active_policies,
        "transactions_today": transactions_today,
        "approved_today": approved_today,
        "denied_today": denied_today,
        "escalated_today": escalated_today,
        "spent_today": spent_today,
        "remaining_daily_budget": remaining_daily_budget,
        "recent_transactions": recent_transactions,
        "recent_audit_events": recent_audit_events,
    }
