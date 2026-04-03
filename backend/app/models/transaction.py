"""Transaction ORM model."""

import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    recipient = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    description = Column(String, nullable=True)
    status = Column(String, nullable=False, default="PENDING")  # Decision status
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    agent = relationship("Agent", back_populates="transactions")
