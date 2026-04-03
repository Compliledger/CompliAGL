"""Audit service — append-only event logging."""

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_event(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    details: str | None = None,
    performed_by: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details=details,
        performed_by=performed_by,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit_logs(
    db: Session,
    entity_type: str | None = None,
    entity_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLog]:
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    return query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()


def get_audit_log(db: Session, log_id: str) -> AuditLog | None:
    return db.query(AuditLog).filter(AuditLog.id == log_id).first()
