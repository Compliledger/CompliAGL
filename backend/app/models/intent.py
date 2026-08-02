"""Intent ORM model — canonical first-class resource.

An **Intent** is a structured, machine-readable proposal of what an actor wants
to do *before* it happens. It is no longer represented only as a generic
amount/currency transaction: it carries an explicit type, action, requested
outcome, structured parameters, correlation/idempotency keys, an integrity
hash, and a lifecycle status.

Monetary values use **integer minor units** (``amount_minor`` +
``amount_currency``); floating-point types are never used for governed money.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import IntentStatus


class Intent(CanonicalMixin, Base):
    """Persistent, structured intent submitted by an actor."""

    __tablename__ = "intents"

    intent_type = Column(String, nullable=False)
    action = Column(String, nullable=False)
    requested_outcome = Column(String, nullable=True)

    # Actor that submitted this intent (ActorIdentity.id).
    actor_id = Column(String, nullable=False, index=True)
    originating_application = Column(String, nullable=True)

    # Structured parameters (JSON text) — not a flat amount/currency pair.
    parameters = Column(Text, nullable=True)

    # Monetary amount in integer minor units (e.g. cents). Never a float.
    amount_minor = Column(BigInteger, nullable=True)
    amount_currency = Column(String, nullable=True)

    correlation_id = Column(String, nullable=True, index=True)
    idempotency_key = Column(String, nullable=True, index=True)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # ``version`` is the intent's own semantic version (distinct from the
    # storage-level ``schema_version`` provided by CanonicalMixin).
    version = Column(String, nullable=False, default="1")
    integrity_hash = Column(String, nullable=True, index=True)

    status = Column(String, nullable=False, default=IntentStatus.PENDING.value)
