"""Audit service — append-only event logging."""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_event(
    db: Session,
    *,
    agent_id: str,
    event_type: str,
    event_summary: str,
    transaction_id: str | None = None,
    event_data: dict[str, Any] | None = None,
) -> AuditLog:
    """Write a single immutable audit event."""
    entry = AuditLog(
        agent_id=agent_id,
        transaction_id=transaction_id,
        event_type=event_type,
        event_summary=event_summary,
        event_data=json.dumps(event_data) if event_data is not None else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit_logs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLog]:
    """Return all audit log entries, newest first."""
    return (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_audit_logs_for_agent(
    db: Session,
    agent_id: str,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLog]:
    """Return audit log entries for a specific agent, newest first."""
    return (
        db.query(AuditLog)
        .filter(AuditLog.agent_id == agent_id)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_audit_logs_for_transaction(
    db: Session,
    transaction_id: str,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLog]:
    """Return audit log entries for a specific transaction, newest first."""
    return (
        db.query(AuditLog)
        .filter(AuditLog.transaction_id == transaction_id)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
