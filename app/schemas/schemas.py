"""Pydantic schemas for CompliAGL API request/response validation.

All status and type fields use the business enums defined in
``app.utils.enums`` to guarantee consistent values across the API surface.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.utils.enums import (
    ActorType,
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


class PolicyCreate(BaseModel):
    agent_id: str
    name: str
    description: Optional[str] = None
    status: PolicyStatus = PolicyStatus.ACTIVE
    max_spend_per_tx: Optional[float] = None
    allowed_assets: Optional[str] = None
    allowed_recipients: Optional[str] = None
    allowed_hours_start_utc: Optional[float] = None
    allowed_hours_end_utc: Optional[float] = None
    risk_level: RiskLevel = RiskLevel.LOW


class PolicyResponse(BaseModel):
    id: str
    agent_id: str
    name: str
    description: Optional[str] = None
    status: PolicyStatus
    max_spend_per_tx: Optional[float] = None
    allowed_assets: Optional[str] = None
    allowed_recipients: Optional[str] = None
    allowed_hours_start_utc: Optional[float] = None
    allowed_hours_end_utc: Optional[float] = None
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
