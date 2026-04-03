"""ProofBundle ORM model."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func

from app.core.database import Base


class ProofBundle(Base):
    __tablename__ = "proof_bundles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    decision = Column(String, nullable=False)
    policy_snapshot = Column(Text, nullable=False)  # JSON: policies evaluated
    evaluation_results = Column(Text, nullable=False)  # JSON: per-rule results
    proof_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
