"""EventDelivery ORM model — persistent per-channel delivery state.

Each :class:`app.models.integration_event.IntegrationEvent` fans out to one
**EventDelivery** per target channel (ProofSync / AuditSync / RegSync). The
delivery row persists the *authorized projection* actually delivered to that
channel (already redacted and scoped), the outbound signature over that
projection, and the reliable-delivery state machine (attempts, retry, and
dead-letter status).

Delivery state is durable so a crash never loses an event: pending and failed
deliveries are retried by the dispatcher, and a delivery that exhausts its retry
budget is moved to ``DEAD_LETTER`` rather than silently dropped.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import EventDeliveryStatus


class EventDelivery(CanonicalMixin, Base):
    """A single channel-scoped, signed delivery of an integration event."""

    __tablename__ = "event_deliveries"

    # Link back to the canonical outbox event (both the deterministic event_id
    # and the surrogate integration_event.id).
    event_id = Column(String, nullable=False, index=True)
    integration_event_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)

    # The destination sync portal (IntegrationChannel) and the adapter used.
    channel = Column(String, nullable=False, index=True)
    adapter = Column(String, nullable=True)

    # The exact authorized, redacted, channel-scoped projection delivered
    # (JSON text) plus its deterministic hash.
    projection = Column(Text, nullable=False, default="{}")
    projection_hash = Column(String, nullable=True, index=True)

    # Outbound signature over ``projection_hash`` so consumers can verify the
    # event originated from CompliAGL and was not tampered with.
    signer_key_id = Column(String, nullable=True)
    signature = Column(Text, nullable=True)

    # --- Reliable-delivery state machine ---
    status = Column(
        String, nullable=False, default=EventDeliveryStatus.PENDING.value
    )
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    last_error = Column(Text, nullable=True)
    external_reference = Column(String, nullable=True, index=True)

    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
