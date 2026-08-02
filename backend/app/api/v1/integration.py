"""Integration / event-feed v1 routes (ProofSync / AuditSync / RegSync).

Exposes the read + operational surface of the integration event system:

* the formal integration **contracts** (event types, channel responsibilities,
  authorized roles),
* the canonical **outbox events** and their per-channel **delivery state**,
* the **scoped feeds** each portal reads (organization + role scoped, redacted),
* operational **dispatch** and **retry** of pending / failed deliveries.

Publishing itself is internal (services emit :class:`EventContract` through the
transactional-outbox publisher); this router never accepts raw events from the
network.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id, get_subscriber_role
from app.core.database import get_db
from app.repositories.canonical import (
    EventDeliveryRepository,
    IntegrationEventRepository,
)
from app.schemas.canonical.integration import (
    ChannelContractResponse,
    ChannelFeedResponse,
    DispatchSummaryResponse,
    EventDeliveryResponse,
    FeedItem,
    IntegrationContractsResponse,
    IntegrationEventResponse,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical.integration import dispatcher
from app.services.canonical.integration.contracts import (
    ALL_CHANNELS,
    CHANNEL_AUTHORIZED_ROLES,
    CHANNEL_RESPONSIBILITIES,
)
from app.services.canonical.integration.scoping import (
    ScopeError,
    authorize,
    parse_channel,
    parse_role,
)
from app.utils.canonical_enums import IntegrationChannel, IntegrationEventType

router = APIRouter(prefix="/integration", tags=["v1:integration"])


# --------------------------------------------------------------------------- #
# Formal contracts (static metadata; the canonical source is CompliLedger)
# --------------------------------------------------------------------------- #
@router.get("/contracts", response_model=IntegrationContractsResponse)
def get_contracts():
    channels = [
        ChannelContractResponse(
            channel=channel.value,
            responsibilities=list(CHANNEL_RESPONSIBILITIES[channel]),
            authorized_roles=sorted(
                r.value for r in CHANNEL_AUTHORIZED_ROLES[channel]
            ),
        )
        for channel in ALL_CHANNELS
    ]
    return IntegrationContractsResponse(
        event_types=[e.value for e in IntegrationEventType],
        channels=channels,
    )


# --------------------------------------------------------------------------- #
# Outbox events + delivery state (tenant scoped)
# --------------------------------------------------------------------------- #
@router.get("/events", response_model=list[IntegrationEventResponse])
def list_events(
    aggregate_type: Optional[str] = None,
    aggregate_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    repo = IntegrationEventRepository(db)
    if aggregate_type and aggregate_id:
        events = repo.list_for_aggregate(
            organization_id,
            aggregate_type,
            aggregate_id,
            skip=skip,
            limit=limit,
        )
    else:
        events = repo.list(organization_id, skip=skip, limit=limit)
    return [orm_to_dict(e) for e in events]


@router.get(
    "/events/{event_id}/deliveries",
    response_model=list[EventDeliveryResponse],
)
def list_event_deliveries(
    event_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    deliveries = EventDeliveryRepository(db).list_for_event(
        organization_id, event_id
    )
    return [orm_to_dict(d) for d in deliveries]


# --------------------------------------------------------------------------- #
# Scoped portal feeds (organization + role scoped, redacted projections)
# --------------------------------------------------------------------------- #
def _resolve_scope(channel_name: str, role_value: str) -> IntegrationChannel:
    try:
        channel = parse_channel(channel_name)
        role = parse_role(role_value)
    except ScopeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        authorize(channel, role)
    except ScopeError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return channel


def _projection_of(delivery) -> dict[str, Any]:
    try:
        return json.loads(delivery.projection or "{}")
    except (ValueError, TypeError):
        return {}


@router.get("/{channel}/feed", response_model=ChannelFeedResponse)
def get_channel_feed(
    channel: str,
    status: Optional[str] = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    subscriber_role: str = Depends(get_subscriber_role),
    db: Session = Depends(get_db),
):
    resolved = _resolve_scope(channel, subscriber_role)
    deliveries = EventDeliveryRepository(db).list_for_channel(
        organization_id,
        resolved.value,
        status=status,
        skip=skip,
        limit=limit,
    )
    items = [
        FeedItem(
            event_id=d.event_id,
            event_type=d.event_type,
            channel=d.channel,
            status=d.status,
            delivered_at=d.delivered_at,
            signer_key_id=d.signer_key_id,
            signature=d.signature,
            projection_hash=d.projection_hash,
            projection=_projection_of(d),
        )
        for d in deliveries
    ]
    return ChannelFeedResponse(
        channel=resolved.value,
        organization_id=organization_id,
        responsibilities=list(CHANNEL_RESPONSIBILITIES[resolved]),
        count=len(items),
        items=items,
    )


@router.get("/{channel}/deliveries", response_model=list[EventDeliveryResponse])
def list_channel_deliveries(
    channel: str,
    status: Optional[str] = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    subscriber_role: str = Depends(get_subscriber_role),
    db: Session = Depends(get_db),
):
    resolved = _resolve_scope(channel, subscriber_role)
    deliveries = EventDeliveryRepository(db).list_for_channel(
        organization_id,
        resolved.value,
        status=status,
        skip=skip,
        limit=limit,
    )
    return [orm_to_dict(d) for d in deliveries]


# --------------------------------------------------------------------------- #
# Operational: dispatch pending, retry a delivery
# --------------------------------------------------------------------------- #
@router.post("/dispatch", response_model=DispatchSummaryResponse)
def dispatch_pending(
    channel: Optional[str] = Query(default=None),
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    resolved: Optional[IntegrationChannel] = None
    if channel is not None:
        try:
            resolved = parse_channel(channel)
        except ScopeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    summary = dispatcher.dispatch_pending(
        db, organization_id, channel=resolved, limit=limit
    )
    return DispatchSummaryResponse(
        considered=summary.considered,
        delivered=summary.delivered,
        failed=summary.failed,
        dead_lettered=summary.dead_lettered,
    )


@router.post(
    "/deliveries/{delivery_id}/retry", response_model=EventDeliveryResponse
)
def retry_delivery(
    delivery_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    delivery = dispatcher.retry_delivery(db, organization_id, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="EventDelivery not found")
    return orm_to_dict(delivery)
