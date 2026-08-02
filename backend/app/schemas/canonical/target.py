"""Target request/response schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase
from app.utils.canonical_enums import TargetType, TrustStatus


class TargetCreate(BaseModel):
    """Payload for creating a target."""

    organization_id: str = Field(..., min_length=1)
    target_type: TargetType
    external_identifier: Optional[str] = None
    owner: Optional[str] = None
    organization: Optional[str] = None
    classification: Optional[str] = None
    trust_status: TrustStatus = TrustStatus.UNKNOWN
    network_or_environment: Optional[str] = None
    target_metadata: Optional[dict[str, Any]] = None


class TargetUpdate(BaseModel):
    """Partial update payload (immutable identifiers are never changed)."""

    owner: Optional[str] = None
    classification: Optional[str] = None
    trust_status: Optional[TrustStatus] = None
    network_or_environment: Optional[str] = None
    target_metadata: Optional[dict[str, Any]] = None


class TargetResponse(CanonicalResponseBase):
    """Target as returned by the API."""

    target_type: str
    external_identifier: Optional[str] = None
    owner: Optional[str] = None
    organization: Optional[str] = None
    classification: Optional[str] = None
    trust_status: str
    network_or_environment: Optional[str] = None
    target_metadata: Optional[dict[str, Any]] = None
