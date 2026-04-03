"""SQLAlchemy models for the CompliAGL governance layer.

All status and type columns use the business enums defined in
``app.utils.enums`` to enforce type safety at the application level.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from app.utils.enums import (
    ActorType,
    ApprovalStatus,
    DecisionResult,
    PolicyStatus,
    ProofStatus,
    RiskLevel,
    TransactionStatus,
)


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Agent(Base):
    """An autonomous software entity with an associated wallet."""

    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=_generate_uuid)
    name = Column(String, nullable=False)
    actor_type = Column(String, nullable=False, default=ActorType.AGENT.value)
    wallet_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    policies = relationship("Policy", back_populates="agent")
    transactions = relationship("Transaction", back_populates="agent")


class Policy(Base):
    """A governance rule set bound to an agent."""

    __tablename__ = "policies"

    id = Column(String, primary_key=True, default=_generate_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default=PolicyStatus.ACTIVE.value)
    max_spend_per_tx = Column(Float, nullable=True)
    allowed_assets = Column(Text, nullable=True)
    allowed_recipients = Column(Text, nullable=True)
    allowed_hours_start_utc = Column(Float, nullable=True)
    allowed_hours_end_utc = Column(Float, nullable=True)
    risk_level = Column(String, nullable=False, default=RiskLevel.LOW.value)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    agent = relationship("Agent", back_populates="policies")


class Transaction(Base):
    """A spend/transfer request originating from an agent wallet."""

    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=_generate_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    amount = Column(Float, nullable=False)
    asset = Column(String, nullable=False)
    recipient = Column(String, nullable=False)
    status = Column(
        String, nullable=False, default=TransactionStatus.SUBMITTED.value
    )
    transaction_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    agent = relationship("Agent", back_populates="transactions")
    decision = relationship(
        "Decision", back_populates="transaction", uselist=False
    )


class Decision(Base):
    """The verdict returned by the Decision Engine for a transaction."""

    __tablename__ = "decisions"

    id = Column(String, primary_key=True, default=_generate_uuid)
    transaction_id = Column(
        String, ForeignKey("transactions.id"), nullable=False
    )
    result = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    rules_evaluated = Column(Integer, nullable=True)
    rules_passed = Column(Integer, nullable=True)
    rules_failed = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    transaction = relationship("Transaction", back_populates="decision")
    proof_record = relationship(
        "ProofRecord", back_populates="decision", uselist=False
    )
    approval_request = relationship(
        "ApprovalRequest", back_populates="decision", uselist=False
    )


class ApprovalRequest(Base):
    """A human-review request created when a decision is ESCALATED."""

    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True, default=_generate_uuid)
    decision_id = Column(String, ForeignKey("decisions.id"), nullable=False)
    reviewer_id = Column(String, nullable=True)
    status = Column(
        String, nullable=False, default=ApprovalStatus.PENDING.value
    )
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)

    decision = relationship("Decision", back_populates="approval_request")


class ProofRecord(Base):
    """A cryptographic attestation of a governance decision."""

    __tablename__ = "proof_records"

    id = Column(String, primary_key=True, default=_generate_uuid)
    decision_id = Column(String, ForeignKey("decisions.id"), nullable=False)
    verdict = Column(String, nullable=False)
    policy_snapshot = Column(Text, nullable=True)
    signature = Column(String, nullable=True)
    status = Column(
        String, nullable=False, default=ProofStatus.GENERATED.value
    )
    created_at = Column(DateTime, default=_utcnow)

    decision = relationship("Decision", back_populates="proof_record")


class AuditLog(Base):
    """Immutable, append-only record of governance events."""

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=_generate_uuid)
    event_type = Column(String, nullable=False)
    actor_type = Column(String, nullable=False)
    actor_id = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
