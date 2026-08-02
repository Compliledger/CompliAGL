"""ActorIdentity request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase
from app.utils.canonical_enums import (
    CanonicalActorType,
    CredentialType,
    RevocationStatus,
    VerificationStatus,
)


class ActorIdentityCreate(BaseModel):
    """Payload for creating an actor identity."""

    organization_id: str = Field(..., min_length=1)
    actor_type: CanonicalActorType
    human_principal_id: Optional[str] = None
    external_account_id: Optional[str] = None
    wallet_or_agent_account_id: Optional[str] = None
    credential_type: CredentialType = CredentialType.NONE
    credential_issuer: Optional[str] = None
    credential_reference: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revocation_status: RevocationStatus = RevocationStatus.ACTIVE
    identity_metadata: Optional[dict[str, Any]] = None


class ActorIdentityUpdate(BaseModel):
    """Partial update payload (immutable ``id`` and tenant are never changed)."""

    verification_status: Optional[VerificationStatus] = None
    credential_issuer: Optional[str] = None
    credential_reference: Optional[str] = None
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revocation_status: Optional[RevocationStatus] = None
    identity_metadata: Optional[dict[str, Any]] = None


class ActorIdentityResponse(CanonicalResponseBase):
    """Actor identity as returned by the API."""

    actor_type: str
    human_principal_id: Optional[str] = None
    external_account_id: Optional[str] = None
    wallet_or_agent_account_id: Optional[str] = None
    credential_type: str
    credential_issuer: Optional[str] = None
    credential_reference: Optional[str] = None
    verification_status: str
    valid_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revocation_status: str
    identity_metadata: Optional[dict[str, Any]] = None
