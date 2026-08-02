"""Change detection — the :class:`ChangeDetector` interface + defaults.

A **ChangeDetector** observes one class of monitored change and, when it fires,
yields a :class:`DetectedChange` describing *what* changed (type, source,
affected object, before/after state hashes, severity, provenance). Detectors are
deliberately small and deterministic so continuous monitoring is auditable: the
same before/after state always produces the same detection (and the same
deterministic event id downstream).

The module also declares the canonical registry of monitored change categories
and the default disposition/severity each category implies. These defaults let
the re-evaluation pipeline behave sensibly without a caller having to spell out
an outcome, while still allowing an explicit override.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional

from app.utils.canonical_enums import (
    DecisionOutcome,
    MonitoringChangeType,
    MonitoringSeverity,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now

# The full set of monitored change categories.
MONITORED_CHANGE_TYPES: frozenset[MonitoringChangeType] = frozenset(
    MonitoringChangeType
)

# Change categories that, by default, mean the prior governed outcome is no
# longer supported: the current decision must be re-evaluated to DENIED and any
# outstanding authorization invalidated.
INVALIDATING_CHANGE_TYPES: frozenset[MonitoringChangeType] = frozenset(
    {
        MonitoringChangeType.EVIDENCE_EXPIRED,
        MonitoringChangeType.EVIDENCE_REVOKED,
        MonitoringChangeType.AUTHORIZATION_EXPIRED,
        MonitoringChangeType.AUTHORIZATION_REVOKED,
        MonitoringChangeType.ACTOR_AUTHORITY_CHANGED,
    }
)

# Change categories that, by default, can restore an APPROVED outcome (e.g. a
# finding resolved with valid evidence, remediation completed).
RESTORATIVE_CHANGE_TYPES: frozenset[MonitoringChangeType] = frozenset(
    {
        MonitoringChangeType.FINDING_STATUS_CHANGED,
        MonitoringChangeType.REMEDIATION_STATUS_CHANGED,
    }
)

# Default deterministic outcome each change category implies when the caller
# does not supply an explicit outcome. Categories not listed default to
# re-evaluation with the prior outcome preserved (a neutral refresh).
DEFAULT_OUTCOME_BY_CHANGE: dict[MonitoringChangeType, DecisionOutcome] = {
    MonitoringChangeType.EVIDENCE_EXPIRED: DecisionOutcome.DENIED,
    MonitoringChangeType.EVIDENCE_REVOKED: DecisionOutcome.DENIED,
    MonitoringChangeType.AUTHORIZATION_EXPIRED: DecisionOutcome.DENIED,
    MonitoringChangeType.AUTHORIZATION_REVOKED: DecisionOutcome.DENIED,
    MonitoringChangeType.ACTOR_AUTHORITY_CHANGED: DecisionOutcome.DENIED,
    MonitoringChangeType.FINDING_STATUS_CHANGED: DecisionOutcome.APPROVED,
    MonitoringChangeType.REMEDIATION_STATUS_CHANGED: DecisionOutcome.APPROVED,
}

# Default severity each change category is reported at.
DEFAULT_SEVERITY_BY_CHANGE: dict[MonitoringChangeType, MonitoringSeverity] = {
    MonitoringChangeType.POLICY_CHANGED: MonitoringSeverity.HIGH,
    MonitoringChangeType.GOVERNANCE_PACKAGE_CHANGED: MonitoringSeverity.HIGH,
    MonitoringChangeType.OPERATIONAL_CONTEXT_CHANGED: MonitoringSeverity.MEDIUM,
    MonitoringChangeType.EVIDENCE_CHANGED: MonitoringSeverity.MEDIUM,
    MonitoringChangeType.EVIDENCE_EXPIRED: MonitoringSeverity.HIGH,
    MonitoringChangeType.EVIDENCE_REVOKED: MonitoringSeverity.CRITICAL,
    MonitoringChangeType.FINDING_STATUS_CHANGED: MonitoringSeverity.MEDIUM,
    MonitoringChangeType.REMEDIATION_STATUS_CHANGED: MonitoringSeverity.MEDIUM,
    MonitoringChangeType.AUTHORIZATION_EXPIRED: MonitoringSeverity.HIGH,
    MonitoringChangeType.AUTHORIZATION_REVOKED: MonitoringSeverity.CRITICAL,
    MonitoringChangeType.EXTERNAL_EXECUTION_RESULT_CHANGED: (
        MonitoringSeverity.MEDIUM
    ),
    MonitoringChangeType.TARGET_STATE_CHANGED: MonitoringSeverity.MEDIUM,
    MonitoringChangeType.ACTOR_AUTHORITY_CHANGED: MonitoringSeverity.CRITICAL,
}


def compute_state_hash(state: Any) -> str:
    """Return the deterministic hash of a monitored object's state snapshot."""
    return hash_dict({"state": state})


def default_severity(change_type: MonitoringChangeType) -> MonitoringSeverity:
    return DEFAULT_SEVERITY_BY_CHANGE.get(change_type, MonitoringSeverity.MEDIUM)


def default_outcome(
    change_type: MonitoringChangeType,
) -> Optional[DecisionOutcome]:
    """Return the default re-evaluation outcome for a change (may be ``None``)."""
    return DEFAULT_OUTCOME_BY_CHANGE.get(change_type)


@dataclass(frozen=True)
class DetectedChange:
    """A single detected monitored change (the detector's output)."""

    change_type: MonitoringChangeType
    source: str
    affected_object_type: str
    affected_object_id: str
    old_state_hash: Optional[str] = None
    new_state_hash: Optional[str] = None
    severity: Optional[MonitoringSeverity] = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    intent_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    detected_at: Optional[datetime] = None

    def resolved_severity(self) -> MonitoringSeverity:
        return self.severity or default_severity(self.change_type)

    def resolved_detected_at(self) -> datetime:
        return self.detected_at or utc_now()


class ChangeDetector(abc.ABC):
    """Interface every concrete change detector implements.

    A detector is scoped to exactly one :class:`MonitoringChangeType`. Given the
    prior and current state of a monitored object it decides whether a material
    change occurred and, if so, yields a :class:`DetectedChange`.
    """

    #: The change category this detector reports.
    change_type: MonitoringChangeType

    @abc.abstractmethod
    def detect(
        self,
        *,
        affected_object_type: str,
        affected_object_id: str,
        old_state: Any = None,
        new_state: Any = None,
        source: str,
        provenance: Optional[Mapping[str, Any]] = None,
        correlation_id: Optional[str] = None,
        intent_id: Optional[str] = None,
        evaluation_id: Optional[str] = None,
    ) -> list[DetectedChange]:
        """Return the detected changes (empty if nothing material changed)."""
        raise NotImplementedError


class StateHashChangeDetector(ChangeDetector):
    """Default detector: fire when an object's state hash changes.

    It compares the deterministic hash of ``old_state`` and ``new_state``; a
    difference (including first observation, when there is no prior state) is a
    material change and produces exactly one :class:`DetectedChange`.
    """

    def __init__(self, change_type: MonitoringChangeType) -> None:
        self.change_type = change_type

    def detect(
        self,
        *,
        affected_object_type: str,
        affected_object_id: str,
        old_state: Any = None,
        new_state: Any = None,
        source: str,
        provenance: Optional[Mapping[str, Any]] = None,
        correlation_id: Optional[str] = None,
        intent_id: Optional[str] = None,
        evaluation_id: Optional[str] = None,
    ) -> list[DetectedChange]:
        old_hash = compute_state_hash(old_state) if old_state is not None else None
        new_hash = compute_state_hash(new_state) if new_state is not None else None
        if old_hash is not None and old_hash == new_hash:
            return []
        return [
            DetectedChange(
                change_type=self.change_type,
                source=source,
                affected_object_type=affected_object_type,
                affected_object_id=affected_object_id,
                old_state_hash=old_hash,
                new_state_hash=new_hash,
                provenance=dict(provenance or {}),
                correlation_id=correlation_id,
                intent_id=intent_id,
                evaluation_id=evaluation_id,
            )
        ]


# A ready-to-use registry of a default state-hash detector per monitored change
# category. A deployment can replace any entry with a bespoke detector.
DETECTOR_REGISTRY: dict[MonitoringChangeType, ChangeDetector] = {
    change_type: StateHashChangeDetector(change_type)
    for change_type in MONITORED_CHANGE_TYPES
}


def get_detector(change_type: MonitoringChangeType) -> ChangeDetector:
    """Return the registered detector for a monitored change category."""
    return DETECTOR_REGISTRY[change_type]
