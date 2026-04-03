"""Policy Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    policy_type: str = "SPEND_LIMIT"
    parameters: dict[str, Any] = {}
    is_active: bool = True
    agent_id: Optional[str] = None
    blocked_vendors: Optional[list[str]] = None
    blocked_chains: Optional[list[str]] = None
    blocked_asset_symbols: Optional[list[str]] = None
    allowed_vendors: Optional[list[str]] = None
    allowed_chains: Optional[list[str]] = None
    allowed_asset_symbols: Optional[list[str]] = None
    per_tx_limit: Optional[float] = None
    daily_budget: Optional[float] = None
    max_transactions_per_day: Optional[int] = None
    require_identity_check_above_amount: Optional[float] = None
    require_approval_above_threshold: Optional[bool] = False
    escalation_threshold: Optional[float] = None


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    policy_type: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    agent_id: Optional[str] = None
    blocked_vendors: Optional[list[str]] = None
    blocked_chains: Optional[list[str]] = None
    blocked_asset_symbols: Optional[list[str]] = None
    allowed_vendors: Optional[list[str]] = None
    allowed_chains: Optional[list[str]] = None
    allowed_asset_symbols: Optional[list[str]] = None
    per_tx_limit: Optional[float] = None
    daily_budget: Optional[float] = None
    max_transactions_per_day: Optional[int] = None
    require_identity_check_above_amount: Optional[float] = None
    require_approval_above_threshold: Optional[bool] = None
    escalation_threshold: Optional[float] = None


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    policy_type: str
    parameters: dict[str, Any] = {}
    is_active: bool
    agent_id: Optional[str] = None
    blocked_vendors: Optional[list[str]] = None
    blocked_chains: Optional[list[str]] = None
    blocked_asset_symbols: Optional[list[str]] = None
    allowed_vendors: Optional[list[str]] = None
    allowed_chains: Optional[list[str]] = None
    allowed_asset_symbols: Optional[list[str]] = None
    per_tx_limit: Optional[float] = None
    daily_budget: Optional[float] = None
    max_transactions_per_day: Optional[int] = None
    require_identity_check_above_amount: Optional[float] = None
    require_approval_above_threshold: Optional[bool] = False
    escalation_threshold: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
