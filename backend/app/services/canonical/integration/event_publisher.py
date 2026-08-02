"""Transactional-outbox event publisher for the sync portals.

Publishing follows the **outbox pattern** for reliability: an
:class:`app.models.integration_event.IntegrationEvent` (the outbox record) and
one :class:`app.models.event_delivery.EventDelivery` per target channel are
written together in a single database transaction. Delivery to the portals is a
separate, retryable step (see :mod:`.dispatcher`), so a crash after the state
change but before delivery never loses an event.

Guarantees implemented here:

* **Reliability** — outbox + delivery rows are persisted atomically.
* **Idempotency** — the deterministic ``event_id`` means re-publishing the same
  logical event is a no-op (the existing outbox event is returned and no
  duplicate deliveries are created).
* **Scoping** — every row carries ``organization_id`` for tenant isolation, and
  each delivery is a channel-scoped, authorized projection.
* **Redaction** — projections never contain raw sensitive evidence.
* **Signing** — each delivered projection is signed over its hash.
"""

from __future__ import annotations

import json
import logging
from typing import Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event_delivery import EventDelivery
from app.models.integration_event import IntegrationEvent
from app.repositories.canonical import (
    EventDeliveryRepository,
    IntegrationEventRepository,
)
from app.services.canonical.integration import event_signing
from app.services.canonical.integration.channel_adapter import get_adapter
from app.services.canonical.integration.contracts import (
    ALL_CHANNELS,
    EventContract,
)
from app.services.canonical.integration.projections import build_projection
from app.utils.canonical_enums import EventDeliveryStatus, IntegrationChannel
from app.utils.hashing import hash_dict

logger = logging.getLogger(__name__)


def _build_delivery(
    contract: EventContract,
    event: IntegrationEvent,
    channel: IntegrationChannel,
) -> EventDelivery:
    projection = build_projection(contract, channel)
    projection_hash = hash_dict(projection)
    signer_key_id, signature = event_signing.sign(projection_hash)
    adapter = get_adapter(channel)
    return EventDelivery(
        organization_id=contract.organization_id,
        event_id=event.event_id,
        integration_event_id=event.id,
        event_type=event.event_type,
        channel=channel.value,
        adapter=adapter.name,
        projection=json.dumps(projection),
        projection_hash=projection_hash,
        signer_key_id=signer_key_id,
        signature=signature,
        status=EventDeliveryStatus.PENDING.value,
        attempts=0,
        max_attempts=int(getattr(settings, "EVENT_MAX_DELIVERY_ATTEMPTS", 5)),
    )


def publish(
    db: Session,
    contract: EventContract,
    *,
    channels: Optional[Iterable[IntegrationChannel]] = None,
) -> IntegrationEvent:
    """Publish an event to the outbox and fan it out to the target channels.

    Idempotent on the contract's deterministic ``event_id``: if the event has
    already been published for the tenant, the existing outbox record is returned
    unchanged and no duplicate deliveries are created.
    """
    org = contract.organization_id
    if not org:
        raise ValueError("organization_id is required to publish an event")

    event_id = contract.event_id()
    repo = IntegrationEventRepository(db)
    existing = repo.get_by_event_id(org, event_id)
    if existing is not None:
        return existing

    target_channels = tuple(channels) if channels is not None else ALL_CHANNELS

    event = IntegrationEvent(
        organization_id=org,
        event_id=event_id,
        event_type=contract.event_type.value,
        aggregate_type=contract.aggregate_type,
        aggregate_id=contract.aggregate_id,
        occurred_at=contract.resolved_occurred_at(),
        references=json.dumps(dict(contract.references)),
        attributes=json.dumps(dict(contract.attributes)),
        sensitive_digest=json.dumps(contract.sensitive_digest()),
        payload_hash=contract.payload_hash(),
    )
    db.add(event)
    # Flush so the surrogate id is populated for the delivery rows, but keep the
    # whole outbox write in one transaction (committed once below).
    db.flush()

    for channel in target_channels:
        db.add(_build_delivery(contract, event, channel))

    db.commit()
    db.refresh(event)
    return event


def emit_safe(
    db: Session,
    contract: EventContract,
    *,
    channels: Optional[Iterable[IntegrationChannel]] = None,
) -> Optional[IntegrationEvent]:
    """Best-effort publish that never raises into the calling service.

    Integration/event publishing must never break the canonical governance flow.
    Any failure is logged and swallowed (with a rollback of the failed outbox
    write); the canonical state change has already been committed by the caller.
    """
    try:
        return publish(db, contract, channels=channels)
    except Exception:  # noqa: BLE001 - integration must never break governance
        logger.exception(
            "Failed to publish integration event %s for %s/%s",
            contract.event_type.value,
            contract.aggregate_type,
            contract.aggregate_id,
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            logger.exception("Rollback after failed event publish also failed")
        return None


def deliveries_for(
    db: Session, organization_id: str, event_id: str
) -> Sequence[EventDelivery]:
    """Return all channel deliveries for a published event."""
    return EventDeliveryRepository(db).list_for_event(organization_id, event_id)
