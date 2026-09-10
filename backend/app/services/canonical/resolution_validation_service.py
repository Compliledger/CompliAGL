"""Resolution validation service.

Determines whether a :class:`Finding` is *actually* resolved by evaluating its
submitted :class:`ResolutionEvidence` for sufficiency against the remediation
plan's ``required_resolution_evidence``, plus (for manual-review findings) an
approving :class:`ReviewRecord`.

Resolution is fail-closed: ``VALIDATED`` requires that every mandatory required
resolution evidence type is satisfied by a *validated* (VALID) evidence item.
Invalid, expired, revoked or stale evidence never validates a resolution, and a
mere "remediation complete" signal is never sufficient.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.repositories.canonical import (
    FindingRepository,
    RemediationPlanRepository,
    ResolutionEvidenceRepository,
    ReviewRecordRepository,
)
from app.services.canonical.errors import NotFoundError
from app.utils.canonical_enums import (
    EvidenceSufficiencyOutcome,
    EvidenceValidationOutcome,
    FindingStatus,
    FindingType,
    RemediationPlanStatus,
    ResolutionValidationOutcome,
    ReviewOutcome,
)

# Validation outcomes that positively demonstrate an invalid resolution attempt
# (as opposed to simply missing evidence).
_INVALID_OUTCOMES = {
    EvidenceValidationOutcome.INVALID.value,
    EvidenceValidationOutcome.EXPIRED.value,
    EvidenceValidationOutcome.REVOKED.value,
    EvidenceValidationOutcome.STALE.value,
    EvidenceValidationOutcome.UNTRUSTED_SOURCE.value,
    EvidenceValidationOutcome.SUBJECT_MISMATCH.value,
    EvidenceValidationOutcome.TARGET_MISMATCH.value,
}


def _load(raw: Optional[str], default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def _mandatory_required_types(plan) -> list[str]:
    if plan is None:
        return []
    required: list[str] = []
    for entry in _load(plan.required_resolution_evidence, []) or []:
        if isinstance(entry, dict) and entry.get("mandatory", True):
            etype = entry.get("evidence_type")
            if etype:
                required.append(str(etype))
    return required


def validate(
    db: Session, organization_id: str, finding_id: str
) -> dict[str, Any]:
    """Validate a finding's resolution and update finding/plan state."""
    org = organization_id
    finding = FindingRepository(db).get(org, finding_id)
    if finding is None:
        raise NotFoundError(f"Finding not found: {finding_id}")

    reason_codes: list[str] = []

    # A terminal finding can never be resolved.
    if finding.terminal:
        finding.resolution_validation_outcome = (
            ResolutionValidationOutcome.REJECTED.value
        )
        finding.status = FindingStatus.TERMINATED.value
        FindingRepository(db).save(finding)
        return {
            "finding_id": finding.finding_id,
            "outcome": ResolutionValidationOutcome.REJECTED.value,
            "sufficiency": EvidenceSufficiencyOutcome.NOT_EVALUABLE.value,
            "reason_codes": ["RESOLUTION_FINDING_TERMINAL"],
            "evidence_results": [],
            "finding_status": finding.status,
        }

    # An escalation-approval finding is never resolved through this path:
    # resolution evidence / a review record cannot substitute for an
    # authority-verified approval + an explicit re-decision. Fail closed and
    # persist the reason so the rejection leaves a trace (not just a returned
    # value). This finding type is also always remediation-INELIGIBLE, so a
    # plan can't exist for it either — this is the second of three barriers.
    if finding.finding_type == FindingType.ESCALATION_APPROVAL_REQUIRED.value:
        codes = ["RESOLUTION_ESCALATION_APPROVAL_PATH_REQUIRED"]
        finding.resolution_validation_outcome = (
            ResolutionValidationOutcome.REJECTED.value
        )
        finding.resolution_reason_codes = json.dumps(codes)
        finding.status = FindingStatus.VALIDATION_FAILED.value
        FindingRepository(db).save(finding)
        return {
            "finding_id": finding.finding_id,
            "outcome": ResolutionValidationOutcome.REJECTED.value,
            "sufficiency": EvidenceSufficiencyOutcome.NOT_EVALUABLE.value,
            "reason_codes": codes,
            "evidence_results": [],
            "finding_status": finding.status,
        }

    plan = RemediationPlanRepository(db).latest_for_finding(org, finding.id)
    evidences = ResolutionEvidenceRepository(db).list_for_finding(org, finding.id)
    reviews = ReviewRecordRepository(db).list_for_finding(org, finding.id)

    satisfied_types: set[str] = set()
    invalid_present = False
    evidence_results: list[dict[str, Any]] = []
    for ev in evidences:
        valid = ev.validation_outcome == EvidenceValidationOutcome.VALID.value
        if valid:
            satisfied_types.add(ev.evidence_type)
        if ev.validation_outcome in _INVALID_OUTCOMES:
            invalid_present = True
        evidence_results.append(
            {
                "resolution_evidence_id": ev.id,
                "evidence_type": ev.evidence_type,
                "validation_outcome": ev.validation_outcome,
                "valid": valid,
            }
        )

    required_types = _mandatory_required_types(plan)
    unmet = [t for t in required_types if t not in satisfied_types]

    review_needed = finding.finding_type == FindingType.MANUAL_REVIEW.value
    review_ok = any(r.outcome == ReviewOutcome.APPROVED.value for r in reviews)

    # --- Deterministic mapping (fail-closed) ------------------------------- #
    if review_needed and not review_ok:
        outcome = ResolutionValidationOutcome.INSUFFICIENT_EVIDENCE.value
        sufficiency = EvidenceSufficiencyOutcome.INSUFFICIENT.value
        reason_codes.append("RESOLUTION_MANUAL_REVIEW_APPROVAL_REQUIRED")
    elif unmet:
        if invalid_present:
            outcome = ResolutionValidationOutcome.REJECTED.value
            sufficiency = EvidenceSufficiencyOutcome.INSUFFICIENT.value
            reason_codes.append("RESOLUTION_EVIDENCE_INVALID")
        else:
            outcome = ResolutionValidationOutcome.INSUFFICIENT_EVIDENCE.value
            sufficiency = EvidenceSufficiencyOutcome.INSUFFICIENT.value
            reason_codes.append("RESOLUTION_EVIDENCE_MISSING")
        reason_codes.extend(f"UNMET_EVIDENCE_{t}" for t in unmet)
    elif not required_types and not review_needed and not satisfied_types:
        # Nothing required and nothing validated — cannot confirm resolution.
        if invalid_present:
            outcome = ResolutionValidationOutcome.REJECTED.value
            reason_codes.append("RESOLUTION_EVIDENCE_INVALID")
        else:
            outcome = ResolutionValidationOutcome.INSUFFICIENT_EVIDENCE.value
            reason_codes.append("RESOLUTION_NO_EVIDENCE")
        sufficiency = EvidenceSufficiencyOutcome.INSUFFICIENT.value
    else:
        outcome = ResolutionValidationOutcome.VALIDATED.value
        sufficiency = EvidenceSufficiencyOutcome.SUFFICIENT.value
        reason_codes.append("RESOLUTION_VALIDATED")
        if review_ok:
            reason_codes.append("RESOLUTION_REVIEW_APPROVED")

    # --- Persist governance-owned state ------------------------------------ #
    finding.resolution_validation_outcome = outcome
    if outcome == ResolutionValidationOutcome.VALIDATED.value:
        if finding.status != FindingStatus.CLOSED.value:
            finding.status = FindingStatus.RESOLVED_PENDING_VALIDATION.value
    else:
        finding.status = FindingStatus.VALIDATION_FAILED.value
    FindingRepository(db).save(finding)

    if plan is not None and plan.status not in {
        RemediationPlanStatus.CANCELLED.value,
    }:
        if outcome == ResolutionValidationOutcome.VALIDATED.value:
            plan.status = RemediationPlanStatus.VALIDATED.value
        else:
            plan.status = RemediationPlanStatus.VALIDATION_FAILED.value
        RemediationPlanRepository(db).save(plan)

    return {
        "finding_id": finding.finding_id,
        "outcome": outcome,
        "sufficiency": sufficiency,
        "reason_codes": reason_codes,
        "evidence_results": evidence_results,
        "finding_status": finding.status,
    }
