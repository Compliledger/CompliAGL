"""Monitoring event service — record changes + publish to the sync portals.

Recording a monitored change is the entry point of the continuous-monitoring
branch. The service:

* derives a **deterministic** ``event_uid`` so re-submitting the same logical
  change is idempotent (the existing event is returned, never duplicated),
* persists an immutable :class:`MonitoringEvent` (it never overwrites any
  governed record),
* publishes a ``monitoring.change_detected`` event to ProofSync / AuditSync /
  RegSync (best-effort; integration never breaks the canonical flow).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.monitoring_event import MonitoringEvent
from app.repositories.canonical import MonitoringEventRepository
from app.services.canonical.monitoring.change_detector import (
    DetectedChange,
    default_severity,
)
from app.utils.canonical_enums import (
    IntegrationEventType,
    MonitoringChangeType,
    MonitoringSeverity,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import ensure_aware, utc_now


def _identity_payload(
    organization_id: str,
    change_type: str,
    affected_object_type: str,
    affected_object_id: str,
    old_state_hash: Optional[str],
    new_state_hash: Optional[str],
    correlation_id: Optional[str],
) -> dict[str, Any]:
    return {
        "organization_id": organization_id,
        "change_type": change_type,
        "affected_object_type": affected_object_type,
        "affected_object_id": affected_object_id,
        "old_state_hash": old_state_hash or "",
        "new_state_hash": new_state_hash or "",
        "correlation_id": correlation_id or "",
    }


def submit_event(
    db: Session,
    organization_id: str,
    *,
    change_type: MonitoringChangeType | str,
    source: str,
    affected_object_type: str,
    affected_object_id: str,
    old_state_hash: Optional[str] = None,
    new_state_hash: Optional[str] = None,
    severity: Optional[MonitoringSeverity | str] = None,
    provenance: Optional[Mapping[str, Any]] = None,
    correlation_id: Optional[str] = None,
    intent_id: Optional[str] = None,
    evaluation_id: Optional[str] = None,
    detected_at: Optional[datetime] = None,
) -> MonitoringEvent:
    """Record a monitored change. Idempotent on the deterministic ``event_uid``."""
    change = MonitoringChangeType(change_type)
    if severity is None:
        severity_value = default_severity(change).value
    else:
        severity_value = MonitoringSeverity(severity).value

    identity = _identity_payload(
        organization_id,
        change.value,
        affected_object_type,
        affected_object_id,
        old_state_hash,
        new_state_hash,
        correlation_id,
    )
    event_uid = "mon-" + hash_dict(identity)[:32]

    repo = MonitoringEventRepository(db)
    existing = repo.get_by_event_uid(organization_id, event_uid)
    if existing is not None:
        return existing

    detected = ensure_aware(detected_at) or utc_now()
    provenance_dict = dict(provenance or {})
    event_hash = hash_dict(
        {
            "identity": identity,
            "source": source,
            "severity": severity_value,
            "detected_at": detected.isoformat(),
            "provenance": provenance_dict,
        }
    )

    event = MonitoringEvent(
        organization_id=organization_id,
        event_uid=event_uid,
        change_type=change.value,
        source=source,
        affected_object_type=affected_object_type,
        affected_object_id=affected_object_id,
        intent_id=intent_id,
        evaluation_id=evaluation_id,
        old_state_hash=old_state_hash,
        new_state_hash=new_state_hash,
        detected_at=detected,
        provenance=json.dumps(provenance_dict),
        severity=severity_value,
        correlation_id=correlation_id,
        event_hash=event_hash,
    )
    event = repo.add(event)

    _publish_change_detected(db, event)
    return event


def submit_detected(
    db: Session, organization_id: str, change: DetectedChange
) -> MonitoringEvent:
    """Record a :class:`DetectedChange` produced by a :class:`ChangeDetector`."""
    return submit_event(
        db,
        organization_id,
        change_type=change.change_type,
        source=change.source,
        affected_object_type=change.affected_object_type,
        affected_object_id=change.affected_object_id,
        old_state_hash=change.old_state_hash,
        new_state_hash=change.new_state_hash,
        severity=change.resolved_severity(),
        provenance=change.provenance,
        correlation_id=change.correlation_id,
        intent_id=change.intent_id,
        evaluation_id=change.evaluation_id,
        detected_at=change.resolved_detected_at(),
    )


def _publish_change_detected(db: Session, event: MonitoringEvent) -> None:
    """Publish ``monitoring.change_detected`` to the sync portals (best-effort)."""
    from app.services.canonical.integration import event_publisher
    from app.services.canonical.integration.contracts import EventContract

    event_publisher.emit_safe(
        db,
        EventContract(
            event_type=IntegrationEventType.MONITORING_CHANGE_DETECTED,
            organization_id=event.organization_id,
            aggregate_type=event.affected_object_type,
            aggregate_id=event.affected_object_id,
            references={
                "monitoring_event_id": event.id,
                "event_uid": event.event_uid,
                "affected_object_type": event.affected_object_type,
                "affected_object_id": event.affected_object_id,
                "intent_id": event.intent_id,
                "evaluation_id": event.evaluation_id,
                "old_state_hash": event.old_state_hash,
                "new_state_hash": event.new_state_hash,
                "correlation_id": event.correlation_id,
            },
            attributes={
                "change_type": event.change_type,
                "source": event.source,
                "severity": event.severity,
                "status": "DETECTED",
            },
            dedup_key=f"monitoring:{event.event_uid}",
            occurred_at=event.detected_at,
        ),
    )


def get(
    db: Session, organization_id: str, monitoring_event_id: str
) -> Optional[MonitoringEvent]:
    return MonitoringEventRepository(db).get(organization_id, monitoring_event_id)


def list_(
    db: Session,
    organization_id: str,
    *,
    change_type: Optional[str] = None,
    affected_object_type: Optional[str] = None,
    affected_object_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[MonitoringEvent]:
    return MonitoringEventRepository(db).list_filtered(
        organization_id,
        change_type=change_type,
        affected_object_type=affected_object_type,
        affected_object_id=affected_object_id,
        correlation_id=correlation_id,
        skip=skip,
        limit=limit,
    )
