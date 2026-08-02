"""ResolutionEvidence service — reuses the governance evidence architecture.

Resolution evidence proves a finding has actually been remediated. Each item is
validated with the **same deterministic validation battery** used for governance
evidence (:mod:`app.services.evidence.evidence_validation_service`), then — when
valid — normalized. The collection of items for a finding is later evaluated for
sufficiency by :mod:`app.services.canonical.resolution_validation_service`.

Submitting evidence is never proof of resolution; only *validated* evidence that
meets the plan's required resolution evidence can drive a re-assessment.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.raw_evidence import RawEvidence
from app.models.resolution_evidence import ResolutionEvidence
from app.repositories.canonical import (
    FindingRepository,
    RemediationPlanRepository,
    ResolutionEvidenceRepository,
)
from app.schemas.canonical.remediation import ResolutionEvidenceSubmit
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.canonical.errors import NotFoundError
from app.services.evidence import evidence_validation_service
from app.utils.canonical_enums import (
    EvidenceCollectionStatus,
    EvidenceValidationOutcome,
    SensitivityClassification,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def _load(raw: Optional[str], default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def _required_evidence_descriptor(plan, evidence_type: str) -> dict[str, Any]:
    """Return the matching required-resolution-evidence descriptor, if any."""
    if plan is None:
        return {}
    for entry in _load(plan.required_resolution_evidence, []) or []:
        if isinstance(entry, dict) and entry.get("evidence_type") == evidence_type:
            return entry
    return {}


def _transient_raw_evidence(
    submit: ResolutionEvidenceSubmit,
    descriptor: dict[str, Any],
    payload_hash: Optional[str],
) -> RawEvidence:
    """Build an unsaved RawEvidence so the shared validator can score it."""
    requirement = {
        "allowed_issuers": descriptor.get("allowed_issuers") or [],
        "freshness_threshold": descriptor.get("freshness_threshold"),
        "expected_subject_id": descriptor.get("expected_subject_id"),
        "expected_target_id": descriptor.get("expected_target_id"),
        "expected_intent_id": descriptor.get("expected_intent_id"),
    }
    provenance = dict(submit.provenance or {})
    provenance.setdefault("requirement", requirement)
    if submit.signature:
        provenance.setdefault("signature_valid", True)

    return RawEvidence(
        organization_id=submit.organization_id,
        collection_job_id="resolution",
        evidence_requirement_id=submit.evidence_type,
        policy_resolution_id=None,
        source_id=submit.source_id or (submit.issuer or "resolution-source"),
        source_type=submit.source_type or "EXTERNAL_APPLICATION",
        subject_id=submit.subject_id,
        target_id=submit.target_id,
        intent_id=submit.intent_id,
        collected_at=utc_now(),
        issued_at=submit.issued_at,
        expires_at=submit.expires_at,
        payload=(json.dumps(submit.payload) if submit.payload is not None else None),
        payload_hash=payload_hash,
        claims=(json.dumps(submit.claims) if submit.claims is not None else None),
        sensitivity=SensitivityClassification.INTERNAL.value,
        issuer=submit.issuer,
        signature=submit.signature,
        provenance=json.dumps(provenance),
        collection_status=EvidenceCollectionStatus.COLLECTED.value,
    )


def submit(db: Session, payload: ResolutionEvidenceSubmit) -> ResolutionEvidence:
    """Persist a resolution-evidence item and validate + normalize it."""
    org = payload.organization_id
    finding = FindingRepository(db).get(org, payload.finding_id)
    if finding is None:
        raise NotFoundError(f"Finding not found: {payload.finding_id}")

    plan = None
    if payload.remediation_plan_id:
        plan = RemediationPlanRepository(db).get(org, payload.remediation_plan_id)
    else:
        plan = RemediationPlanRepository(db).latest_for_finding(org, finding.id)

    descriptor = _required_evidence_descriptor(plan, payload.evidence_type)

    # Deterministic payload hash (integrity binding, mirrors RawEvidence).
    if payload.payload is not None:
        payload_hash = hash_dict({"payload": payload.payload})
    elif payload.claims is not None:
        payload_hash = hash_dict({"claims": payload.claims})
    else:
        payload_hash = None

    raw = _transient_raw_evidence(payload, descriptor, payload_hash)
    verdict = evidence_validation_service.evaluate(raw)

    # Normalization: expose validated claims downstream only when the item is
    # actually VALID (never normalize invalid/expired/revoked evidence).
    normalized_claims = None
    if verdict["outcome"] == EvidenceValidationOutcome.VALID.value:
        normalized_claims = payload.claims or (payload.payload or {})

    now = utc_now()
    result_hash = hash_dict(
        {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "finding_id": finding.id,
            "evidence_type": payload.evidence_type,
            "payload_hash": payload_hash,
            "outcome": verdict["outcome"],
            "checks": verdict["checks"],
        }
    )

    obj = ResolutionEvidence(
        organization_id=org,
        finding_id=finding.id,
        remediation_plan_id=(plan.id if plan is not None else None),
        evidence_type=payload.evidence_type,
        source_id=raw.source_id,
        source_type=raw.source_type,
        subject_id=payload.subject_id,
        target_id=payload.target_id,
        intent_id=payload.intent_id,
        collected_at=now,
        issued_at=payload.issued_at,
        expires_at=payload.expires_at,
        payload=(json.dumps(payload.payload) if payload.payload is not None else None),
        payload_hash=payload_hash,
        claims=(json.dumps(payload.claims) if payload.claims is not None else None),
        sensitivity=SensitivityClassification.INTERNAL.value,
        issuer=payload.issuer,
        signature=payload.signature,
        provenance=json.dumps(payload.provenance or {}),
        collection_status=EvidenceCollectionStatus.COLLECTED.value,
        validation_outcome=verdict["outcome"],
        validation_checks=json.dumps(verdict["checks"]),
        normalized_claims=(
            json.dumps(normalized_claims) if normalized_claims is not None else None
        ),
        reason_codes=json.dumps(verdict["reason_codes"]),
        submitted_via=payload.submitted_via,
        result_hash=result_hash,
        validated_at=now,
    )
    return ResolutionEvidenceRepository(db).add(obj)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[ResolutionEvidence]:
    return ResolutionEvidenceRepository(db).get(organization_id, resource_id)


def list_for_finding(
    db: Session, organization_id: str, finding_id: str
) -> Sequence[ResolutionEvidence]:
    return ResolutionEvidenceRepository(db).list_for_finding(
        organization_id, finding_id
    )
