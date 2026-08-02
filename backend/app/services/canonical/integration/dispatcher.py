"""Reliable dispatcher for outbox event deliveries.

The dispatcher is the second half of the transactional outbox: it reads
persisted, pending (or retryable failed) :class:`EventDelivery` rows and delivers
their signed projections to the channel adapters. It implements the reliable
delivery guarantees:

* **Retry** — a transient failure increments ``attempts`` and re-arms the
  delivery (``FAILED`` with a back-off ``next_retry_at``).
* **Dead-letter** — once ``attempts`` reaches ``max_attempts`` the delivery is
  moved to ``DEAD_LETTER`` instead of being silently dropped or retried forever.
* **At-least-once + idempotent** — a delivered projection carries a deterministic
  ``event_id`` so an idempotent consumer can deduplicate re-deliveries.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event_delivery import EventDelivery
from app.repositories.canonical import EventDeliveryRepository
from app.services.canonical.integration.channel_adapter import (
    ChannelDeliveryResult,
    SignedEventDelivery,
    get_adapter,
)
from app.utils.canonical_enums import EventDeliveryStatus, IntegrationChannel
from app.utils.timestamps import ensure_aware, utc_now

logger = logging.getLogger(__name__)


@dataclass
class DispatchSummary:
    """Aggregate outcome of a dispatch sweep."""

    considered: int = 0
    delivered: int = 0
    failed: int = 0
    dead_lettered: int = 0


def _to_signed(delivery: EventDelivery) -> SignedEventDelivery:
    try:
        projection = json.loads(delivery.projection or "{}")
    except (ValueError, TypeError):
        projection = {}
    return SignedEventDelivery(
        channel=IntegrationChannel(delivery.channel),
        event_id=delivery.event_id,
        event_type=delivery.event_type,
        organization_id=delivery.organization_id,
        projection=projection,
        projection_hash=delivery.projection_hash or "",
        signer_key_id=delivery.signer_key_id or "",
        signature=delivery.signature or "",
    )


def _is_due(delivery: EventDelivery, now) -> bool:
    """Whether a delivery is eligible for a (re)attempt now."""
    if delivery.status == EventDeliveryStatus.PENDING.value:
        return True
    if delivery.status != EventDeliveryStatus.FAILED.value:
        return False
    retry_at = ensure_aware(delivery.next_retry_at)
    return retry_at is None or retry_at <= now


def dispatch_delivery(db: Session, delivery: EventDelivery) -> EventDelivery:
    """Attempt a single delivery and persist the resulting state."""
    repo = EventDeliveryRepository(db)
    now = utc_now()
    delivery.attempts = (delivery.attempts or 0) + 1
    delivery.dispatched_at = now

    adapter = get_adapter(IntegrationChannel(delivery.channel))
    try:
        result: ChannelDeliveryResult = adapter.deliver(_to_signed(delivery))
    except Exception as exc:  # noqa: BLE001 - adapter failures are handled below
        result = ChannelDeliveryResult(accepted=False, detail=str(exc))

    if result.accepted:
        delivery.status = EventDeliveryStatus.DELIVERED.value
        delivery.delivered_at = now
        delivery.external_reference = result.external_reference
        delivery.last_error = None
        delivery.next_retry_at = None
        return repo.save(delivery)

    delivery.last_error = result.detail or "delivery rejected"
    if delivery.attempts >= (delivery.max_attempts or 0):
        delivery.status = EventDeliveryStatus.DEAD_LETTER.value
        delivery.next_retry_at = None
    else:
        delivery.status = EventDeliveryStatus.FAILED.value
        backoff = int(getattr(settings, "EVENT_RETRY_BACKOFF_SECONDS", 30))
        delivery.next_retry_at = now + timedelta(
            seconds=backoff * delivery.attempts
        )
    return repo.save(delivery)


def dispatch_pending(
    db: Session,
    organization_id: str,
    *,
    channel: Optional[IntegrationChannel] = None,
    limit: int = 100,
) -> DispatchSummary:
    """Dispatch all due deliveries for a tenant (optionally one channel)."""
    repo = EventDeliveryRepository(db)
    candidates: Sequence[EventDelivery] = repo.list_deliverable(
        organization_id,
        channel=channel.value if channel is not None else None,
        limit=limit,
    )
    now = utc_now()
    summary = DispatchSummary()
    for delivery in candidates:
        if not _is_due(delivery, now):
            continue
        summary.considered += 1
        updated = dispatch_delivery(db, delivery)
        if updated.status == EventDeliveryStatus.DELIVERED.value:
            summary.delivered += 1
        elif updated.status == EventDeliveryStatus.DEAD_LETTER.value:
            summary.dead_lettered += 1
        else:
            summary.failed += 1
    return summary


def retry_delivery(
    db: Session, organization_id: str, delivery_id: str
) -> Optional[EventDelivery]:
    """Force a re-attempt of a specific FAILED or DEAD_LETTER delivery."""
    repo = EventDeliveryRepository(db)
    delivery = repo.get(organization_id, delivery_id)
    if delivery is None:
        return None
    if delivery.status == EventDeliveryStatus.DELIVERED.value:
        return delivery
    # A manual retry clears the back-off gate and re-attempts immediately.
    delivery.next_retry_at = None
    if delivery.status == EventDeliveryStatus.DEAD_LETTER.value:
        # Re-open the dead-lettered delivery for one more attempt.
        delivery.status = EventDeliveryStatus.FAILED.value
    return dispatch_delivery(db, delivery)
