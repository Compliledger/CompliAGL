"""DevSync adapter interface and outbound payload.

DevSync is the integration surface for **technical / developer-actionable**
findings and remediation plans. CompliAGL dispatches a finding and its plan to a
DevSync system through a formal adapter and receives inbound status/evidence
callbacks in return.

DevSync is **never** the source of truth for governance. The adapter is an
outbound/inbound transport only: CompliAGL retains the canonical finding and
remediation state, and a DevSync callback never by itself resolves a finding.
"""

from __future__ import annotations

import abc
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class DevSyncOutboundPayload:
    """The canonical outbound payload delivered to a DevSync system."""

    finding_id: str
    source_decision_id: Optional[str]
    callback_reference: str
    # Affected actor / system / target the developer must act on.
    affected_actor_id: Optional[str] = None
    affected_target_id: Optional[str] = None
    affected_system: Optional[str] = None
    control_ids: list[str] = field(default_factory=list)
    requirement_ids: list[str] = field(default_factory=list)
    severity: Optional[str] = None
    remediation_plan_id: Optional[str] = None
    remediation_instructions: list[dict[str, Any]] = field(default_factory=list)
    required_resolution_evidence: list[dict[str, Any]] = field(default_factory=list)
    due_date: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DevSyncDispatchResult:
    """The result of an outbound dispatch, as reported by the adapter."""

    accepted: bool
    external_reference: Optional[str] = None
    detail: Optional[str] = None


class DevSyncAdapter(abc.ABC):
    """Formal outbound adapter contract for a DevSync system."""

    name: str = "devsync"

    @abc.abstractmethod
    def dispatch(self, payload: DevSyncOutboundPayload) -> DevSyncDispatchResult:
        """Deliver the outbound payload to the DevSync system."""
        raise NotImplementedError


class InMemoryDevSyncAdapter(DevSyncAdapter):
    """Default adapter that records dispatched payloads in memory.

    Used as the safe default and in tests. It accepts every dispatch and mints a
    synthetic external reference, but performs no external I/O — so it can never
    become an implicit source of truth.
    """

    name = "in_memory"

    def __init__(self) -> None:
        self.dispatched: list[DevSyncOutboundPayload] = []

    def dispatch(self, payload: DevSyncOutboundPayload) -> DevSyncDispatchResult:
        self.dispatched.append(payload)
        return DevSyncDispatchResult(
            accepted=True,
            external_reference=f"devsync-{uuid.uuid4().hex[:12]}",
            detail="accepted",
        )


# Adapter registry. A deployment registers its real DevSync adapter here.
_ADAPTERS: dict[str, DevSyncAdapter] = {}
_DEFAULT_ADAPTER = InMemoryDevSyncAdapter()


def register_adapter(adapter: DevSyncAdapter) -> None:
    """Register a DevSync adapter under its ``name``."""
    _ADAPTERS[adapter.name] = adapter


def get_adapter(name: Optional[str] = None) -> DevSyncAdapter:
    """Return the named adapter, or the default in-memory adapter."""
    if name and name in _ADAPTERS:
        return _ADAPTERS[name]
    if name and name == _DEFAULT_ADAPTER.name:
        return _DEFAULT_ADAPTER
    if not name:
        return _DEFAULT_ADAPTER
    # Unknown adapter name -> fall back to the safe default.
    return _DEFAULT_ADAPTER
