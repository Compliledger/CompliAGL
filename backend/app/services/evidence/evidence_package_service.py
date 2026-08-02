"""Canonical Evidence Package assembly.

The package is the final, deterministic bundle for one evaluation. It references
the normalized evidence collected for that evaluation, maps evidence back to the
requirements and controls it satisfies, and enumerates the missing and invalid
evidence **explicitly** so an absent or rejected item can never be silently
treated as satisfied.

The package projection is public-safe: it carries only ids, binding references,
issuers and **hashes** — never a raw or sensitive payload. The ``package_hash``
is computed over that projection, so publishing it (e.g. anchoring on a
blockchain) never leaks a sensitive payload.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.canonical_evidence_package import CanonicalEvidencePackage
from app.models.evidence_collection_job import EvidenceCollectionJob
from app.repositories.canonical import (
    CanonicalEvidencePackageRepository,
    EvidenceRequirementSetRepository,
    EvidenceValidationResultRepository,
    NormalizedEvidenceRepository,
    RawEvidenceRepository,
)
from app.utils.canonical_enums import (
    EvidenceValidationOutcome,
    RequiredEvidenceState,
)
from app.utils.hashing import hash_dict


def _load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def build_package(
    db: Session, organization_id: str, job: EvidenceCollectionJob
) -> CanonicalEvidencePackage:
    """Assemble and persist the canonical evidence package for a job."""
    evidence_set = EvidenceRequirementSetRepository(db).get(
        organization_id, job.evidence_requirement_set_id
    )
    requirements = (
        _load(evidence_set.evidence_requirements, []) if evidence_set else []
    ) or []

    normalized = NormalizedEvidenceRepository(db).list_for_job(
        organization_id, job.id
    )
    validations = EvidenceValidationResultRepository(db).list_for_job(
        organization_id, job.id
    )

    # normalized evidence grouped by requirement.
    normalized_by_req: dict[str, list[Any]] = {}
    normalized_refs: list[dict[str, Any]] = []
    for norm in normalized:
        normalized_by_req.setdefault(norm.evidence_requirement_id, []).append(
            norm
        )
        normalized_refs.append(
            {
                "normalized_evidence_id": norm.id,
                "raw_evidence_id": norm.raw_evidence_id,
                "evidence_requirement_id": norm.evidence_requirement_id,
                "evidence_type": norm.evidence_type,
                "subject": norm.subject,
                "target": norm.target,
                "source": norm.source,
                "issuer": norm.issuer,
                "validation_status": norm.validation_status,
                "source_payload_hash": norm.source_payload_hash,
                "normalized_payload_hash": norm.normalized_payload_hash,
                "provenance_reference": norm.provenance_reference,
            }
        )
    normalized_refs.sort(key=lambda r: (r["evidence_requirement_id"] or ""))

    # invalid evidence — every non-VALID validation result.
    invalid_evidence: list[dict[str, Any]] = []
    for val in validations:
        if val.outcome != EvidenceValidationOutcome.VALID.value:
            invalid_evidence.append(
                {
                    "raw_evidence_id": val.raw_evidence_id,
                    "evidence_requirement_id": val.evidence_requirement_id,
                    "outcome": val.outcome,
                }
            )
    invalid_evidence.sort(key=lambda r: (r["evidence_requirement_id"] or ""))

    # requirement & control mappings + missing evidence.
    requirement_mappings: list[dict[str, Any]] = []
    control_accumulator: dict[str, dict[str, Any]] = {}
    missing_evidence: list[dict[str, Any]] = []

    for req in requirements:
        if not isinstance(req, dict):
            continue
        req_id = req.get("evidence_requirement_id")
        state = req.get("state")
        mandatory = bool(req.get("mandatory", True))
        control_ids = list(req.get("control_ids") or [])
        norm_items = normalized_by_req.get(req_id, [])
        satisfied = len(norm_items) > 0

        if state in (
            RequiredEvidenceState.REQUIRED.value,
            RequiredEvidenceState.CONDITIONAL.value,
            RequiredEvidenceState.OPTIONAL.value,
        ):
            requirement_mappings.append(
                {
                    "evidence_requirement_id": req_id,
                    "state": state,
                    "mandatory": mandatory,
                    "control_ids": control_ids,
                    "requirement_ids": list(req.get("requirement_ids") or []),
                    "satisfied": satisfied,
                    "normalized_evidence_ids": [n.id for n in norm_items],
                }
            )
            for cid in control_ids:
                entry = control_accumulator.setdefault(
                    cid,
                    {
                        "control_id": cid,
                        "evidence_requirement_ids": [],
                        "satisfied_requirement_ids": [],
                        "unsatisfied_requirement_ids": [],
                    },
                )
                entry["evidence_requirement_ids"].append(req_id)
                if satisfied:
                    entry["satisfied_requirement_ids"].append(req_id)
                else:
                    entry["unsatisfied_requirement_ids"].append(req_id)

        # Mandatory REQUIRED evidence without a valid normalized item is missing.
        if (
            not satisfied
            and mandatory
            and state == RequiredEvidenceState.REQUIRED.value
        ):
            missing_evidence.append(
                {
                    "evidence_requirement_id": req_id,
                    "evidence_type": req.get("evidence_type"),
                    "reason": "NO_VALID_EVIDENCE",
                }
            )
        elif state == RequiredEvidenceState.UNRESOLVED.value:
            missing_evidence.append(
                {
                    "evidence_requirement_id": req_id,
                    "evidence_type": req.get("evidence_type"),
                    "reason": "UNRESOLVED_REQUIREMENT",
                }
            )

    # Requirements the plan could not resolve to any connector are also missing.
    for item in _load(job.unresolved, []) or []:
        if not isinstance(item, dict):
            continue
        missing_evidence.append(
            {
                "evidence_requirement_id": item.get("evidence_requirement_id"),
                "evidence_type": item.get("evidence_type"),
                "reason": item.get("reason", "UNRESOLVED"),
            }
        )

    # Deduplicate missing entries by (requirement_id, reason), keep order.
    seen: set[tuple] = set()
    deduped_missing: list[dict[str, Any]] = []
    for m in missing_evidence:
        key = (m.get("evidence_requirement_id"), m.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        deduped_missing.append(m)
    deduped_missing.sort(key=lambda r: (r["evidence_requirement_id"] or "", r["reason"]))

    requirement_mappings.sort(key=lambda r: (r["evidence_requirement_id"] or ""))
    control_mappings = [
        control_accumulator[k] for k in sorted(control_accumulator)
    ]

    reason_codes = ["EVIDENCE_PACKAGE_BUILT"]
    if deduped_missing:
        reason_codes.append("EVIDENCE_PACKAGE_HAS_MISSING")
    if invalid_evidence:
        reason_codes.append("EVIDENCE_PACKAGE_HAS_INVALID")
    if not deduped_missing and not invalid_evidence and normalized_refs:
        reason_codes.append("EVIDENCE_PACKAGE_COMPLETE")

    package_hash = hash_dict(
        {
            "evaluation_id": job.policy_resolution_id,
            "collection_job_id": job.id,
            "normalized_evidence_references": normalized_refs,
            "requirement_mappings": requirement_mappings,
            "control_mappings": control_mappings,
            "missing_evidence": deduped_missing,
            "invalid_evidence": invalid_evidence,
        }
    )

    package = CanonicalEvidencePackage(
        organization_id=organization_id,
        evaluation_id=job.policy_resolution_id,
        policy_resolution_id=job.policy_resolution_id,
        evidence_requirement_set_id=job.evidence_requirement_set_id,
        collection_job_id=job.id,
        normalized_evidence_references=json.dumps(normalized_refs),
        requirement_mappings=json.dumps(requirement_mappings),
        control_mappings=json.dumps(control_mappings),
        missing_evidence=json.dumps(deduped_missing),
        invalid_evidence=json.dumps(invalid_evidence),
        reason_codes=json.dumps(reason_codes),
        package_hash=package_hash,
    )
    return CanonicalEvidencePackageRepository(db).add(package)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[CanonicalEvidencePackage]:
    return CanonicalEvidencePackageRepository(db).get(
        organization_id, resource_id
    )


def latest_for_evaluation(
    db: Session, organization_id: str, evaluation_id: str
) -> Optional[CanonicalEvidencePackage]:
    return CanonicalEvidencePackageRepository(db).latest_for_evaluation(
        organization_id, evaluation_id
    )
