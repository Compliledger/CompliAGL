"""Approval ORM model."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func

from app.core.database import Base


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    reviewer_id = Column(String, nullable=True)
    action = Column(String, nullable=False)  # APPROVE / DENY
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
