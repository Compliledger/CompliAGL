"""Intent request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase
from app.utils.canonical_enums import IntentStatus, IntentType


class IntentCreate(BaseModel):
    """Payload for creating an intent.

    Monetary amounts use **integer minor units** (``amount_minor``) plus a
    currency code — never a floating-point value.
    """

    organization_id: str = Field(..., min_length=1)
    intent_type: IntentType
    action: str = Field(..., min_length=1)
    requested_outcome: Optional[str] = None
    actor_id: str = Field(..., min_length=1)
    originating_application: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None
    amount_minor: Optional[int] = Field(default=None, ge=0)
    amount_currency: Optional[str] = Field(default=None, max_length=16)
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    expires_at: Optional[datetime] = None
    version: str = "1"


class IntentUpdate(BaseModel):
    """Partial update payload (immutable identifiers are never changed)."""

    requested_outcome: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class IntentResponse(CanonicalResponseBase):
    """Intent as returned by the API."""

    intent_type: str
    action: str
    requested_outcome: Optional[str] = None
    actor_id: str
    originating_application: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None
    amount_minor: Optional[int] = None
    amount_currency: Optional[str] = None
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    submitted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    version: str
    integrity_hash: Optional[str] = None
    status: str


class IntentStatusUpdate(BaseModel):
    """Explicit lifecycle transition request for an intent."""

    status: IntentStatus
