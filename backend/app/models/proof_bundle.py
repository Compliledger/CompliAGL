"""ProofBundle ORM model."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func

from app.core.database import Base


class ProofBundle(Base):
    __tablename__ = "proof_bundles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    module = Column(String, nullable=False, default="CompliAGL")
    entity_id = Column(String, nullable=False)
    rule_version_used = Column(String, nullable=False)
    decision_result = Column(String, nullable=False)
    evaluation_context = Column(Text, nullable=False)  # JSON
    reason_codes = Column(Text, nullable=False)  # JSON array
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    bundle_hash = Column(String, nullable=False)
    proof_status = Column(String, nullable=False, default="GENERATED")
    anchor_metadata = Column(Text, nullable=True)  # JSON, optional
