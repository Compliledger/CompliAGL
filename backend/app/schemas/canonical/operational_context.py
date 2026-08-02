"""OperationalContext request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase
from app.utils.canonical_enums import EnvironmentType


class OperationalContextCreate(BaseModel):
    """Payload for creating an operational context snapshot.

    State snapshots are free-form JSON objects. Any monetary values inside them
    must use integer minor units — never floating-point values.
    """

    organization_id: str = Field(..., min_length=1)
    business_unit: Optional[str] = None
    jurisdiction: Optional[str] = None
    environment: EnvironmentType = EnvironmentType.PRODUCTION
    context_timestamp: Optional[datetime] = None
    risk_state: Optional[dict[str, Any]] = None
    account_state: Optional[dict[str, Any]] = None
    allowance_state: Optional[dict[str, Any]] = None
    merchant_state: Optional[dict[str, Any]] = None
    asset_state: Optional[dict[str, Any]] = None
    network_state: Optional[dict[str, Any]] = None
    operational_state_snapshot: Optional[dict[str, Any]] = None
    source_references: Optional[list[Any]] = None


class OperationalContextUpdate(BaseModel):
    """Partial update payload (immutable identifiers are never changed)."""

    risk_state: Optional[dict[str, Any]] = None
    account_state: Optional[dict[str, Any]] = None
    allowance_state: Optional[dict[str, Any]] = None
    merchant_state: Optional[dict[str, Any]] = None
    asset_state: Optional[dict[str, Any]] = None
    network_state: Optional[dict[str, Any]] = None
    operational_state_snapshot: Optional[dict[str, Any]] = None
    source_references: Optional[list[Any]] = None


class OperationalContextResponse(CanonicalResponseBase):
    """Operational context as returned by the API."""

    business_unit: Optional[str] = None
    jurisdiction: Optional[str] = None
    environment: str
    context_timestamp: Optional[datetime] = None
    risk_state: Optional[dict[str, Any]] = None
    account_state: Optional[dict[str, Any]] = None
    allowance_state: Optional[dict[str, Any]] = None
    merchant_state: Optional[dict[str, Any]] = None
    asset_state: Optional[dict[str, Any]] = None
    network_state: Optional[dict[str, Any]] = None
    operational_state_snapshot: Optional[dict[str, Any]] = None
    source_references: Optional[list[Any]] = None
    context_hash: Optional[str] = None
