"""Pydantic schemas for CompliAGL API request/response validation.

All status and type fields use the business enums defined in
``app.utils.enums`` to guarantee consistent values across the API surface.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.enums import (
    ActorType,
    AuditEventType,
    ApprovalStatus,
    DecisionResult,
    PolicyStatus,
    ProofStatus,
    RiskLevel,
    TransactionStatus,
)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class AgentCreate(BaseModel):
    name: str
    actor_type: ActorType = ActorType.AGENT
    wallet_address: str
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    metadata_json: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    actor_type: ActorType
    wallet_address: str
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    is_active: bool = True
    metadata_json: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def _validate_non_negative(value: float | None, field_name: str) -> float | None:
    if value is not None and value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


class PolicyCreate(BaseModel):
    agent_id: str
    policy_name: str
    status: PolicyStatus = PolicyStatus.ACTIVE
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
    require_identity_check_above_amount: Optional[float] = Field(default=None, ge=0)
    max_transactions_per_day: Optional[int] = Field(default=None, ge=1)
    timezone: str = "UTC"
    rule_version: str = "v1"
    risk_level: RiskLevel = RiskLevel.LOW

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
    status: Optional[PolicyStatus] = None
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
    risk_level: Optional[RiskLevel] = None

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
    agent_id: str
    policy_name: str
    status: PolicyStatus
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
    risk_level: RiskLevel
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


class TransactionCreate(BaseModel):
    agent_id: str
    amount: float = Field(..., gt=0)
    asset: str
    recipient: str


class TransactionResponse(BaseModel):
    id: str
    agent_id: str
    amount: float
    asset: str
    recipient: str
    status: TransactionStatus
    transaction_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


class DecisionResponse(BaseModel):
    id: str
    transaction_id: str
    result: DecisionResult
    reason: Optional[str] = None
    rules_evaluated: Optional[int] = None
    rules_passed: Optional[int] = None
    rules_failed: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Approval Request
# ---------------------------------------------------------------------------


class ApprovalRequestCreate(BaseModel):
    decision_id: str
    reviewer_id: Optional[str] = None


class ApprovalRequestResponse(BaseModel):
    id: str
    decision_id: str
    reviewer_id: Optional[str] = None
    status: ApprovalStatus
    review_note: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Proof Record
# ---------------------------------------------------------------------------


class ProofRecordResponse(BaseModel):
    id: str
    decision_id: str
    verdict: DecisionResult
    policy_snapshot: Optional[str] = None
    signature: Optional[str] = None
    status: ProofStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


class AuditLogResponse(BaseModel):
    id: str
    agent_id: str
    transaction_id: Optional[str] = None
    event_type: AuditEventType
    event_summary: str
    event_data: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
