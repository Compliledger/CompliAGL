"""Policy Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    agent_id: str
    policy_name: str
    status: str = "ACTIVE"
    daily_budget: float = Field(default=0.0, ge=0)
    per_tx_limit: float = Field(default=0.0, ge=0)
    escalation_threshold: float = Field(default=0.0, ge=0)
    allowed_vendors: list[str] = Field(default_factory=list)
    blocked_vendors: list[str] = Field(default_factory=list)
    allowed_chains: list[str] = Field(default_factory=list)
    blocked_chains: list[str] = Field(default_factory=list)
    allowed_asset_symbols: list[str] = Field(default_factory=list)
    blocked_asset_symbols: list[str] = Field(default_factory=list)
    require_approval_above_threshold: bool = False
    require_identity_check_above_amount: Optional[float] = Field(default=None, ge=0)
    max_transactions_per_day: Optional[int] = Field(default=None, ge=1)
    timezone: str = "UTC"
    rule_version: str = "v1"


class PolicyUpdate(BaseModel):
    policy_name: Optional[str] = None
    status: Optional[str] = None
    daily_budget: Optional[float] = Field(default=None, ge=0)
    per_tx_limit: Optional[float] = Field(default=None, ge=0)
    escalation_threshold: Optional[float] = Field(default=None, ge=0)
    allowed_vendors: Optional[list[str]] = None
    blocked_vendors: Optional[list[str]] = None
    allowed_chains: Optional[list[str]] = None
    blocked_chains: Optional[list[str]] = None
    allowed_asset_symbols: Optional[list[str]] = None
    blocked_asset_symbols: Optional[list[str]] = None
    require_approval_above_threshold: Optional[bool] = None
    require_identity_check_above_amount: Optional[float] = Field(default=None, ge=0)
    max_transactions_per_day: Optional[int] = Field(default=None, ge=1)
    timezone: Optional[str] = None
    rule_version: Optional[str] = None


class PolicyResponse(BaseModel):
    id: str
    agent_id: str
    policy_name: str
    status: str
    daily_budget: float
    per_tx_limit: float
    escalation_threshold: float
    allowed_vendors: list[str] = Field(default_factory=list)
    blocked_vendors: list[str] = Field(default_factory=list)
    allowed_chains: list[str] = Field(default_factory=list)
    blocked_chains: list[str] = Field(default_factory=list)
    allowed_asset_symbols: list[str] = Field(default_factory=list)
    blocked_asset_symbols: list[str] = Field(default_factory=list)
    require_approval_above_threshold: bool
    require_identity_check_above_amount: Optional[float] = None
    max_transactions_per_day: Optional[int] = None
    timezone: str
    rule_version: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
