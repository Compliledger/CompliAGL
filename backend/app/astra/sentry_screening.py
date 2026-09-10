"""Thin wrapper over the real SENTRY sanctions-screening connector.

``request_sanctions_screening`` (the AIRA tool) lands here. This is a direct
call to the production connector
(``connectors/harborstone_sentry_screening.py``) -- not a nested model call --
so the screening result AIRA reasons about is the same integrity-hashed
evidence contract the decision pipeline consumes.

The collected item is also persisted as a :class:`~app.models.raw_evidence.RawEvidence`
row so there is a durable audit record that AIRA delegated this screening to
SENTRY, with what subject and why. It is anchored under a synthetic
``collection_job_id`` (``astra-delegated-screening:<correlation_id>``) because
a delegated screening is not part of an evidence-collection job -- the
authoritative screening that feeds a decision is still collected inside
``governed_action_service.propose``'s pipeline, where this connector is
registered by default.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.harborstone_package import (
    EV_SCREENING,
    SCREENING_EVIDENCE_TYPE,
    SCREENING_ISSUER,
)
from app.models.raw_evidence import RawEvidence
from app.repositories.canonical import RawEvidenceRepository
from app.services.evidence.connectors.base import CollectRequest
from app.services.evidence.connectors.harborstone_sentry_screening import (
    harborstone_sentry_screening_connector,
)
from app.utils.canonical_enums import EvidenceSourceType
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now

logger = logging.getLogger(__name__)

_REQUESTING_AGENT_ID = "agent:harborstone:aira"
_SCREENING_AGENT_ID = "agent:harborstone:sentry"

# Keys copied verbatim from the connector's claims into the tool return value.
_RETURNED_CLAIM_KEYS = (
    "screening_id",
    "result",
    "match_count",
    "risk_level",
    "requires_human_review",
    "screened_at",
    "subject",
    "scope",
    "screening_source",
    "simulation",
    "simulation_note",
    "integrity_hash",
)


def run_screening(
    db: Session,
    *,
    organization_id: str,
    case_id: str,
    correlation_id: str,
    subject_id: str,
    subject_type: str = "wallet",
    reason: Optional[str] = None,
) -> dict[str, Any]:
    """Delegate one screening to SENTRY, persist the evidence, return the result."""
    request = CollectRequest(
        evidence_requirement_id=EV_SCREENING,
        evidence_type=SCREENING_EVIDENCE_TYPE,
        source_type=EvidenceSourceType.EXTERNAL_APPLICATION.value,
        subject_id=subject_id,
        target_id=subject_id,
        intent_id=correlation_id,
        allowed_issuers=[SCREENING_ISSUER],
    )
    connector = harborstone_sentry_screening_connector()
    result = connector.collect(request)
    claims = result.claims or {}

    raw = _persist_raw_evidence(
        db,
        organization_id=organization_id,
        case_id=case_id,
        correlation_id=correlation_id,
        connector_id=connector.connector_id,
        source_type=connector.source_type,
        trusted_issuers=connector.trusted_issuers,
        result=result,
        subject_type=subject_type,
        reason=reason,
    )

    logger.info(
        "astra: AIRA delegated sanctions screening of %r (%s) to SENTRY -> %s "
        "(raw_evidence=%s, correlation=%s)",
        subject_id,
        subject_type,
        claims.get("result"),
        raw.id,
        correlation_id,
    )

    out: dict[str, Any] = {
        key: claims[key] for key in _RETURNED_CLAIM_KEYS if key in claims
    }
    out.update(
        {
            "raw_evidence_id": raw.id,
            "delegated_by": _REQUESTING_AGENT_ID,
            "screened_by": _SCREENING_AGENT_ID,
            "case_id": case_id,
        }
    )
    return out


def _persist_raw_evidence(
    db: Session,
    *,
    organization_id: str,
    case_id: str,
    correlation_id: str,
    connector_id: str,
    source_type: str,
    trusted_issuers: tuple[str, ...],
    result,
    subject_type: str,
    reason: Optional[str],
) -> RawEvidence:
    """Persist the collected screening item with delegation provenance.

    Shape mirrors ``evidence_orchestration_service._persist_raw_evidence`` for
    the fields validation/normalization read, plus a ``delegation`` block.
    """
    claims = result.claims or {}
    provenance = {
        "connector_id": connector_id,
        "source_id": connector_id,
        "source_type": source_type,
        "is_mock": False,
        "collected_via": "astra_tool_delegation",
        "connector_trusted_issuers": list(trusted_issuers),
        "signature_valid": result.signature_valid,
        "revoked": bool(result.revoked),
        "source_authority": bool(result.source_authority),
        "delegation": {
            "requesting_agent_id": _REQUESTING_AGENT_ID,
            "screening_agent_id": _SCREENING_AGENT_ID,
            "correlation_id": correlation_id,
            "case_id": case_id,
            "subject_type": subject_type,
            "reason": reason,
        },
        "requirement": {
            "evidence_type": SCREENING_EVIDENCE_TYPE,
            "allowed_issuers": [SCREENING_ISSUER],
            "expected_subject_id": result.subject_id,
            "expected_target_id": result.target_id,
            "expected_intent_id": result.intent_id,
        },
    }
    raw = RawEvidence(
        organization_id=organization_id,
        collection_job_id=f"astra-delegated-screening:{correlation_id}",
        evidence_requirement_id=EV_SCREENING,
        policy_resolution_id=None,
        source_id=connector_id,
        source_type=source_type,
        subject_id=result.subject_id,
        target_id=result.target_id,
        intent_id=result.intent_id,
        collected_at=utc_now(),
        issued_at=result.issued_at,
        expires_at=result.expires_at,
        payload=None,
        payload_reference=None,
        payload_hash=hash_dict({"claims": claims}),
        claims=json.dumps(claims),
        sensitivity=result.sensitivity,
        issuer=result.issuer,
        signature=result.signature,
        provenance=json.dumps(provenance),
        collection_status=result.status,
        error=result.error,
    )
    return RawEvidenceRepository(db).add(raw)
