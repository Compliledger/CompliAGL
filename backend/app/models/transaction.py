"""Transaction ORM model."""

import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.utils.enums import TransactionStatus


class Transaction(Base):
    """A proposed agent wallet action that CompliAGL evaluates."""

    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    wallet_address = Column(String, nullable=False)
    vendor = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    asset_symbol = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    destination = Column(String, nullable=False)
    memo = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    status = Column(
        String, nullable=False, default=TransactionStatus.SUBMITTED.value
    )
    decision_result = Column(String, nullable=True)
    decision_reason_summary = Column(String, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agent = relationship("Agent", back_populates="transactions")
