"""Policy Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _validate_non_negative(value: float | None, field_name: str) -> float | None:
    if value is not None and value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


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
    require_identity_check_above_amount: Optional[float] = None
    max_transactions_per_day: Optional[int] = None
    timezone: str = "UTC"
    rule_version: str = "v1"

    @field_validator("require_identity_check_above_amount")
    @classmethod
    def _non_negative_identity_amount(cls, v: float | None) -> float | None:
        return _validate_non_negative(v, "require_identity_check_above_amount")

    @field_validator("max_transactions_per_day")
    @classmethod
    def _positive_max_tx(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("max_transactions_per_day must be non-negative")
        return v


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
    require_identity_check_above_amount: Optional[float] = None
    max_transactions_per_day: Optional[int] = None
    timezone: Optional[str] = None
    rule_version: Optional[str] = None

    @field_validator("require_identity_check_above_amount")
    @classmethod
    def _non_negative_identity_amount(cls, v: float | None) -> float | None:
        return _validate_non_negative(v, "require_identity_check_above_amount")

    @field_validator("max_transactions_per_day")
    @classmethod
    def _positive_max_tx(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("max_transactions_per_day must be non-negative")
        return v


class PolicyResponse(BaseModel):
    id: str
    agent_id: Optional[str] = None
    policy_name: Optional[str] = None
    status: Optional[str] = None
    daily_budget: Optional[float] = None
    per_tx_limit: Optional[float] = None
    escalation_threshold: Optional[float] = None
    allowed_vendors: Optional[list[str]] = Field(default_factory=list)
    blocked_vendors: Optional[list[str]] = Field(default_factory=list)
    allowed_chains: Optional[list[str]] = Field(default_factory=list)
    blocked_chains: Optional[list[str]] = Field(default_factory=list)
    allowed_asset_symbols: Optional[list[str]] = Field(default_factory=list)
    blocked_asset_symbols: Optional[list[str]] = Field(default_factory=list)
    require_approval_above_threshold: Optional[bool] = None
    require_identity_check_above_amount: Optional[float] = None
    max_transactions_per_day: Optional[int] = None
    timezone: Optional[str] = None
    rule_version: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    policy_type: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
