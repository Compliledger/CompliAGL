"""AuditLog ORM model."""

import uuid

from sqlalchemy import Column, DateTime, String, Text, func

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String, nullable=False)  # e.g. "transaction"
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(Text, nullable=True)  # JSON string
    performed_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
