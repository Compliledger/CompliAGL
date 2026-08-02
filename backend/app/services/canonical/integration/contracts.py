"""Formal integration contracts for the sync portals.

This module is the single source of truth for the ProofSync, AuditSync and
RegSync integration surfaces. It defines:

* the **channel responsibilities** each portal is contractually scoped to,
* the **authorized subscriber roles** per channel (role scoping),
* the :class:`EventContract` an internal producer emits, cleanly separating
  safe *references* / non-sensitive *attributes* from *sensitive* fields that
  must never leave CompliAGL in the clear.

CompliAGL / CompliLedger remains the canonical proof source. These portals are
integration surfaces only — they receive references and authorized projections,
never a duplicated copy of the canonical proof store.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional

from app.utils.canonical_enums import (
    IntegrationChannel,
    IntegrationEventType,
    SubscriberRole,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import ensure_aware, utc_now

# --------------------------------------------------------------------------- #
# Channel responsibilities (formal contract, kept in code so it is testable)
# --------------------------------------------------------------------------- #
CHANNEL_RESPONSIBILITIES: dict[IntegrationChannel, tuple[str, ...]] = {
    IntegrationChannel.PROOFSYNC: (
        "client-facing real-time governance and assurance feed",
        "current assessment status",
        "decision status",
        "proof verification status",
        "finding status",
        "remediation status",
        "change history",
        "continuous-monitoring events",
    ),
    IntegrationChannel.AUDITSYNC: (
        "auditor-authorized access",
        "evidence references",
        "proof verification",
        "assessment history",
        "finding history",
        "remediation history",
        "resolution history",
        "scoped exports",
    ),
    IntegrationChannel.REGSYNC: (
        "regulator-authorized access",
        "regulation-specific proof views",
        "applicable requirement mapping",
        "independent verification",
        "continuous supervision",
        "examination history",
        "regulatory reporting",
    ),
}

# --------------------------------------------------------------------------- #
# Role scoping: which subscriber roles may read each channel
# --------------------------------------------------------------------------- #
CHANNEL_AUTHORIZED_ROLES: dict[IntegrationChannel, frozenset[SubscriberRole]] = {
    IntegrationChannel.PROOFSYNC: frozenset(
        {
            SubscriberRole.CLIENT,
            SubscriberRole.GOVERNANCE_ADMIN,
            SubscriberRole.COMPLILEDGER_SERVICE,
        }
    ),
    IntegrationChannel.AUDITSYNC: frozenset(
        {
            SubscriberRole.AUDITOR,
            SubscriberRole.COMPLILEDGER_SERVICE,
        }
    ),
    IntegrationChannel.REGSYNC: frozenset(
        {
            SubscriberRole.REGULATOR,
            SubscriberRole.COMPLILEDGER_SERVICE,
        }
    ),
}

# Every event type is, by default, published to all three portals — each with
# its own authorized, redacted projection. A producer may still narrow the
# channel set explicitly.
ALL_CHANNELS: tuple[IntegrationChannel, ...] = (
    IntegrationChannel.PROOFSYNC,
    IntegrationChannel.AUDITSYNC,
    IntegrationChannel.REGSYNC,
)


@dataclass(frozen=True)
class EventContract:
    """A canonical governance/assurance event ready to be published.

    ``references`` and ``attributes`` are always safe to project to an
    authorized channel. ``sensitive`` holds fields that must never be emitted in
    the clear — the publisher stores and forwards only their digests.
    """

    event_type: IntegrationEventType
    organization_id: str
    aggregate_type: str
    aggregate_id: str
    # Safe references: ids and hashes that point back to the canonical source.
    references: Mapping[str, Any] = field(default_factory=dict)
    # Non-sensitive attributes safe to project (status, outcome, counts, ...).
    attributes: Mapping[str, Any] = field(default_factory=dict)
    # Sensitive fields (raw evidence, PII payloads). NEVER forwarded in clear.
    sensitive: Mapping[str, Any] = field(default_factory=dict)
    occurred_at: Optional[datetime] = None
    # Optional extra discriminator folded into the deterministic event_id so two
    # genuinely distinct events on the same aggregate do not collide.
    dedup_key: Optional[str] = None

    # ------------------------------------------------------------------ #
    def resolved_occurred_at(self) -> datetime:
        return ensure_aware(self.occurred_at) or utc_now()

    def identity_payload(self) -> dict[str, Any]:
        """The deterministic identity used to derive a stable ``event_id``."""
        return {
            "event_type": self.event_type.value,
            "organization_id": self.organization_id,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "dedup_key": self.dedup_key or "",
        }

    def event_id(self) -> str:
        """Deterministic, idempotent identifier for this logical event."""
        return "evt-" + hash_dict(self.identity_payload())[:32]

    def sensitive_digest(self) -> dict[str, Any]:
        """Return per-field digests of sensitive values (never the raw value)."""
        digest: dict[str, Any] = {}
        for key, value in dict(self.sensitive).items():
            digest[key] = {
                "redacted": True,
                "sha256": hash_dict({"value": value}),
            }
        return digest

    def content_payload(self) -> dict[str, Any]:
        """The canonical (non-sensitive) content bound by ``payload_hash``."""
        return {
            "event_id": self.event_id(),
            "event_type": self.event_type.value,
            "organization_id": self.organization_id,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "occurred_at": self.resolved_occurred_at().isoformat(),
            "references": dict(self.references),
            "attributes": dict(self.attributes),
            "sensitive_digest": self.sensitive_digest(),
        }

    def payload_hash(self) -> str:
        return hash_dict(self.content_payload())

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data
