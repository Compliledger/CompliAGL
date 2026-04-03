"""Policy ORM model."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text, func

from app.core.database import Base


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    policy_type = Column(String, nullable=False)  # SPEND_LIMIT, ALLOWLIST, etc.
    parameters = Column(Text, nullable=False, default="{}")  # JSON string
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
