"""Channel adapter interfaces for the sync portals.

Each sync portal (ProofSync / AuditSync / RegSync) is reached through a formal
outbound **channel adapter**. The adapter is a transport contract only: the
actual portal code lives in separate repositories, so this module ships the
abstract interface plus safe in-memory default adapters used by default and in
tests.

An adapter receives a fully-formed, already-redacted and signed
:class:`SignedEventDelivery` and reports whether the portal accepted it. It can
never become an implicit source of truth: CompliAGL / CompliLedger retains the
canonical proof store and the outbox delivery state.
"""

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from app.utils.canonical_enums import IntegrationChannel


@dataclass(frozen=True)
class SignedEventDelivery:
    """The signed, channel-scoped projection handed to a channel adapter."""

    channel: IntegrationChannel
    event_id: str
    event_type: str
    organization_id: str
    projection: dict[str, Any]
    projection_hash: str
    signer_key_id: str
    signature: str


@dataclass(frozen=True)
class ChannelDeliveryResult:
    """The result of an outbound delivery, as reported by an adapter."""

    accepted: bool
    external_reference: Optional[str] = None
    detail: Optional[str] = None


class IntegrationChannelAdapter(abc.ABC):
    """Formal outbound adapter contract for a sync portal channel."""

    channel: IntegrationChannel
    name: str = "channel"

    @abc.abstractmethod
    def deliver(self, delivery: SignedEventDelivery) -> ChannelDeliveryResult:
        """Deliver a signed, authorized projection to the portal."""
        raise NotImplementedError


class InMemoryChannelAdapter(IntegrationChannelAdapter):
    """Default adapter that records deliveries in memory.

    Used as the safe default and in tests. It accepts every delivery and mints a
    synthetic external reference but performs no external I/O, so it can never
    become an implicit source of truth.
    """

    def __init__(self, channel: IntegrationChannel) -> None:
        self.channel = channel
        self.name = f"in_memory:{channel.value.lower()}"
        self.delivered: list[SignedEventDelivery] = []

    def deliver(self, delivery: SignedEventDelivery) -> ChannelDeliveryResult:
        self.delivered.append(delivery)
        return ChannelDeliveryResult(
            accepted=True,
            external_reference=f"{self.channel.value.lower()}-{uuid.uuid4().hex[:12]}",
            detail="accepted",
        )


class ProofSyncAdapter(InMemoryChannelAdapter):
    """Adapter contract for the client-facing ProofSync portal."""

    def __init__(self) -> None:
        super().__init__(IntegrationChannel.PROOFSYNC)
        self.name = "proofsync:in_memory"


class AuditSyncAdapter(InMemoryChannelAdapter):
    """Adapter contract for the auditor-facing AuditSync portal."""

    def __init__(self) -> None:
        super().__init__(IntegrationChannel.AUDITSYNC)
        self.name = "auditsync:in_memory"


class RegSyncAdapter(InMemoryChannelAdapter):
    """Adapter contract for the regulator-facing RegSync portal."""

    def __init__(self) -> None:
        super().__init__(IntegrationChannel.REGSYNC)
        self.name = "regsync:in_memory"


# Per-channel adapter registry. A deployment registers its real portal adapter
# for a channel here; otherwise the safe in-memory default is used.
_DEFAULT_ADAPTERS: dict[IntegrationChannel, IntegrationChannelAdapter] = {
    IntegrationChannel.PROOFSYNC: ProofSyncAdapter(),
    IntegrationChannel.AUDITSYNC: AuditSyncAdapter(),
    IntegrationChannel.REGSYNC: RegSyncAdapter(),
}
_ADAPTERS: dict[IntegrationChannel, IntegrationChannelAdapter] = {}


def register_adapter(adapter: IntegrationChannelAdapter) -> None:
    """Register an adapter for its channel."""
    _ADAPTERS[adapter.channel] = adapter


def reset_adapters() -> None:
    """Clear all registered overrides (restores the in-memory defaults)."""
    _ADAPTERS.clear()


def get_adapter(channel: IntegrationChannel) -> IntegrationChannelAdapter:
    """Return the registered adapter for ``channel`` or the safe default."""
    return _ADAPTERS.get(channel) or _DEFAULT_ADAPTERS[channel]
