"""IntegrationEvent ORM model — the transactional outbox record.

An **IntegrationEvent** is the canonical, persisted outbox entry for a single
governance / assurance event that the ProofSync, AuditSync and RegSync portals
consume. CompliAGL / CompliLedger remains the canonical proof source: the event
only ever carries *references* (ids, hashes) and non-sensitive attributes, plus
**digests** (hashes) of any sensitive fields — never the raw sensitive evidence
itself. The portals are integration surfaces, never a duplicate proof store.

The outbox row is written in the *same database transaction* as the state change
that produced it, and one :class:`app.models.event_delivery.EventDelivery` row is
created per target channel so delivery can be retried independently and reliably.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class IntegrationEvent(CanonicalMixin, Base):
    """A canonical outbox event awaiting fan-out to the sync portals."""

    __tablename__ = "integration_events"

    # Deterministic, idempotent event identity. The same logical event always
    # hashes to the same ``event_id`` so re-publishing is a no-op and downstream
    # consumers can deduplicate on it.
    event_id = Column(String, nullable=False, index=True)

    event_type = Column(String, nullable=False, index=True)

    # The canonical aggregate this event is about (e.g. Decision, Finding,
    # AIProof) and its identifier — always a *reference*, never a copy.
    aggregate_type = Column(String, nullable=False, index=True)
    aggregate_id = Column(String, nullable=False, index=True)

    occurred_at = Column(DateTime(timezone=True), nullable=True)

    # Safe references (ids + hashes) and non-sensitive attributes (JSON text).
    references = Column(Text, nullable=False, default="{}")
    attributes = Column(Text, nullable=False, default="{}")
    # Digests (hashes) of sensitive fields — the raw values are NEVER stored or
    # forwarded through the outbox. This is defense in depth for redaction.
    sensitive_digest = Column(Text, nullable=False, default="{}")

    # Deterministic hash binding the canonical event content together.
    payload_hash = Column(String, nullable=True, index=True)
