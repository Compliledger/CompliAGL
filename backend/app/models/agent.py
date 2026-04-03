"""Agent ORM model."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.utils.enums import ActorType


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    wallet_address = Column(String, unique=True, nullable=False)
    actor_type = Column(String, nullable=False, default=ActorType.AGENT.value)
    owner_name = Column(String, nullable=True)
    owner_email = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    transactions = relationship("Transaction", back_populates="agent")
