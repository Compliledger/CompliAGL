"""AuditLog ORM model."""

import uuid

from sqlalchemy import Column, DateTime, String, Text, func

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False, index=True)
    transaction_id = Column(String, nullable=True, index=True)
    event_type = Column(String, nullable=False)
    event_summary = Column(String, nullable=False)
    event_data = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
