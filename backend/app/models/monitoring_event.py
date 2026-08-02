"""MonitoringEvent ORM model — canonical first-class continuous-monitoring record.

A **MonitoringEvent** is the durable, auditable statement that a monitored change
occurred in the canonical CompliAGL lifecycle. It captures *what* changed, *where
it came from*, the *before/after* state hashes, *when* it was detected, its
*provenance*, *severity* and a *correlation id* so a stream of related changes can
be traced end to end.

The event never overwrites any governed record — it is an immutable trigger the
impact-analysis and re-evaluation pipeline consumes to produce new records.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import MonitoringSeverity


class MonitoringEvent(CanonicalMixin, Base):
    """Persistent continuous-monitoring change event."""

    __tablename__ = "monitoring_events"

    # Stable, deterministic, human-referenceable identifier (distinct from the
    # surrogate ``id``). Recomputing the same logical change yields the same
    # ``event_uid`` so re-submission is idempotent.
    event_uid = Column(String, nullable=False, index=True)

    # The monitored change category (see :class:`MonitoringChangeType`).
    change_type = Column(String, nullable=False, index=True)

    # Where the change was observed (connector / engine / portal / manual).
    source = Column(String, nullable=False)

    # The canonical object that changed — always a *reference* (type + id).
    affected_object_type = Column(String, nullable=False, index=True)
    affected_object_id = Column(String, nullable=False, index=True)

    # Optional lifecycle scoping references so impact analysis and re-evaluation
    # can be deterministically bound to a single intent / evaluation.
    intent_id = Column(String, nullable=True, index=True)
    evaluation_id = Column(String, nullable=True, index=True)

    # Before / after state hashes bounding the change.
    old_state_hash = Column(String, nullable=True)
    new_state_hash = Column(String, nullable=True)

    detected_at = Column(DateTime(timezone=True), nullable=True)

    # Provenance of the change (JSON text): who/what observed it, source refs.
    provenance = Column(Text, nullable=False, default="{}")

    severity = Column(
        String, nullable=False, default=MonitoringSeverity.MEDIUM.value
    )

    # Correlation id threading related changes across the lifecycle.
    correlation_id = Column(String, nullable=True, index=True)

    # Deterministic hash binding the immutable event content together.
    event_hash = Column(String, nullable=True, index=True)
