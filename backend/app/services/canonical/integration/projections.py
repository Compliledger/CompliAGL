"""Authorized, redacted per-channel projections.

A **projection** is the channel-scoped view of an event actually delivered to a
sync portal. Projections enforce the core privacy contract:

* **Raw sensitive evidence is never sent by default.** The event's ``sensitive``
  fields are reduced to digests (hashes) plus a ``redacted`` marker — the raw
  values never appear in any projection.
* **References and authorized projections are sent instead.** Safe references
  (ids, hashes) and non-sensitive attributes are always projected, and each
  channel additionally receives a view aligned to its contractual responsibility
  (assurance / audit / regulatory).

CompliAGL / CompliLedger stays the canonical source; a portal follows the
references back to CompliAGL to fetch anything a projection deliberately omits.
"""

from __future__ import annotations

from typing import Any

from app.services.canonical.integration.contracts import EventContract
from app.utils.canonical_enums import IntegrationChannel


def _regulatory_view(references: dict[str, Any], attributes: dict[str, Any]) -> dict[str, Any]:
    """RegSync: regulation-scoped, requirement-mapped, independently verifiable."""
    return {
        "applicable_requirement_ids": references.get("requirement_ids", []),
        "regulation_references": references.get("regulation_references", []),
        "proof_reference": references.get("proof_hash")
        or references.get("proof_id"),
        "anchor_reference": references.get("anchor_tx_id"),
        "verification_reference": references.get("verification_url"),
        "supervision_status": attributes.get("status")
        or attributes.get("outcome"),
    }


def _audit_view(references: dict[str, Any], attributes: dict[str, Any]) -> dict[str, Any]:
    """AuditSync: evidence references + history, still redacted by default."""
    return {
        "evidence_references": references.get("evidence_references", []),
        "proof_reference": references.get("proof_hash")
        or references.get("proof_id"),
        "anchor_reference": references.get("anchor_tx_id"),
        "assessment_reference": references.get("assessment_id"),
        "decision_reference": references.get("decision_id"),
        "finding_reference": references.get("finding_id"),
        "history_status": attributes.get("status") or attributes.get("outcome"),
    }


def _assurance_view(references: dict[str, Any], attributes: dict[str, Any]) -> dict[str, Any]:
    """ProofSync: client-facing current status / assurance snapshot."""
    return {
        "current_status": attributes.get("status") or attributes.get("outcome"),
        "proof_verification_status": attributes.get("proof_verification_status")
        or references.get("verification_url"),
        "proof_reference": references.get("proof_hash")
        or references.get("proof_id"),
    }


_CHANNEL_VIEW_BUILDERS = {
    IntegrationChannel.PROOFSYNC: _assurance_view,
    IntegrationChannel.AUDITSYNC: _audit_view,
    IntegrationChannel.REGSYNC: _regulatory_view,
}

_CHANNEL_VIEW_KEY = {
    IntegrationChannel.PROOFSYNC: "assurance_view",
    IntegrationChannel.AUDITSYNC: "audit_view",
    IntegrationChannel.REGSYNC: "regulatory_view",
}


def build_projection(
    contract: EventContract, channel: IntegrationChannel
) -> dict[str, Any]:
    """Build the authorized, redacted projection for ``channel``.

    The result contains only safe references, non-sensitive attributes and
    per-field digests of sensitive values — never raw sensitive evidence.
    """
    references = dict(contract.references)
    attributes = dict(contract.attributes)

    projection: dict[str, Any] = {
        "event_id": contract.event_id(),
        "event_type": contract.event_type.value,
        "schema_version": 1,
        "organization_id": contract.organization_id,
        "occurred_at": contract.resolved_occurred_at().isoformat(),
        "aggregate_type": contract.aggregate_type,
        "aggregate_id": contract.aggregate_id,
        "channel": channel.value,
        "canonical_source": "compliledger",
        "references": references,
        "attributes": attributes,
        # Sensitive fields are only ever present as redaction markers + digests.
        "redacted_fields": contract.sensitive_digest(),
    }

    view_builder = _CHANNEL_VIEW_BUILDERS[channel]
    projection[_CHANNEL_VIEW_KEY[channel]] = view_builder(references, attributes)
    return projection
