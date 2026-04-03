"""Policy ORM model."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    policy_type = Column(String, nullable=False)  # SPEND_LIMIT, ALLOWLIST, etc.
    parameters = Column(Text, nullable=False, default="{}")  # JSON string
    is_active = Column(Boolean, default=True)

    # --- Blocked / Allowed lists (JSON-encoded arrays) ---
    blocked_vendors = Column(Text, nullable=True, default="[]")
    blocked_chains = Column(Text, nullable=True, default="[]")
    blocked_asset_symbols = Column(Text, nullable=True, default="[]")
    allowed_vendors = Column(Text, nullable=True, default="[]")
    allowed_chains = Column(Text, nullable=True, default="[]")
    allowed_asset_symbols = Column(Text, nullable=True, default="[]")

    # --- Spend limits ---
    per_tx_limit = Column(Float, nullable=True)
    daily_budget = Column(Float, nullable=True)
    max_transactions_per_day = Column(Integer, nullable=True)

    # --- Escalation thresholds ---
    require_identity_check_above_amount = Column(Float, nullable=True)
    require_approval_above_threshold = Column(Boolean, nullable=True, default=False)
    escalation_threshold = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    agent = relationship("Agent", back_populates="policies")
