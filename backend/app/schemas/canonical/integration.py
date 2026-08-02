"""Integration / event-feed request & response schemas.

Read-facing schemas for the ProofSync, AuditSync and RegSync integration
contracts: outbox events, per-channel delivery state, feed projections and
dispatch summaries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase


class IntegrationEventResponse(CanonicalResponseBase):
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: Optional[datetime] = None
    references: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    sensitive_digest: dict[str, Any] = Field(default_factory=dict)
    payload_hash: Optional[str] = None


class EventDeliveryResponse(CanonicalResponseBase):
    event_id: str
    integration_event_id: str
    event_type: str
    channel: str
    adapter: Optional[str] = None
    projection: dict[str, Any] = Field(default_factory=dict)
    projection_hash: Optional[str] = None
    signer_key_id: Optional[str] = None
    signature: Optional[str] = None
    status: str
    attempts: int
    max_attempts: int
    last_error: Optional[str] = None
    external_reference: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None


class FeedItem(BaseModel):
    """A single authorized, redacted projection as seen by a portal."""

    event_id: str
    event_type: str
    channel: str
    status: str
    delivered_at: Optional[datetime] = None
    signer_key_id: Optional[str] = None
    signature: Optional[str] = None
    projection_hash: Optional[str] = None
    projection: dict[str, Any] = Field(default_factory=dict)


class ChannelFeedResponse(BaseModel):
    channel: str
    organization_id: str
    responsibilities: list[str] = Field(default_factory=list)
    count: int
    items: list[FeedItem] = Field(default_factory=list)


class DispatchSummaryResponse(BaseModel):
    considered: int
    delivered: int
    failed: int
    dead_lettered: int


class ChannelContractResponse(BaseModel):
    channel: str
    responsibilities: list[str] = Field(default_factory=list)
    authorized_roles: list[str] = Field(default_factory=list)


class IntegrationContractsResponse(BaseModel):
    canonical_source: str = "compliledger"
    event_types: list[str] = Field(default_factory=list)
    channels: list[ChannelContractResponse] = Field(default_factory=list)
