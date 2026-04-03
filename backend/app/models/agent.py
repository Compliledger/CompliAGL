"""Agent ORM model."""

import uuid

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    wallet_address = Column(String, nullable=True)
    status = Column(String, nullable=False, default="ACTIVE")
    role = Column(String, nullable=True, default="agent")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    transactions = relationship("Transaction", back_populates="agent")
    policies = relationship("Policy", back_populates="agent")
