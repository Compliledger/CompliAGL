"""Evidence Sufficiency service — deterministic runtime stage.

Evidence Sufficiency runs **after** evidence collection / normalization (which
produces the :class:`CanonicalEvidencePackage`) and **before** formal Control
Evaluation. It is a persistent, first-class stage.

For one evaluation it evaluates the :class:`CanonicalEvidencePackage` against the
:class:`EvidenceRequirementSet`. Per evidence requirement it produces one of:

* ``SATISFIED`` — enough *valid normalized* evidence to meet the cardinality,
* ``PARTIAL`` — some valid normalized evidence, but below the cardinality,
* ``MISSING`` — no evidence at all for the requirement,
* ``INVALID`` — evidence exists but every item failed validation (invalid /
  expired / revoked / untrusted source / subject or target mismatch),
* ``STALE`` — evidence exists but is stale,
* ``NOT_EVALUABLE`` — the requirement could not be evaluated (unresolved basis
  or an indeterminate validation),
* ``MANUAL_REVIEW_REQUIRED`` — the requirement's validation method mandates a
  human sign-off.

The overall outcome is one of ``SUFFICIENT``, ``PARTIAL``, ``INSUFFICIENT``,
``NOT_EVALUABLE`` or ``MANUAL_REVIEW_REQUIRED``. Crucially, ``SUFFICIENT`` is
**never** produced when any mandatory evidence requirement is missing, invalid,
stale, expired, revoked or not evaluable.

No LLM and no dynamic code execution is used anywhere in this module — every
step is deterministic and reproducible via the recorded hashes.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.evidence_sufficiency import EvidenceSufficiency
from app.repositories.canonical import (
    CanonicalEvidencePackageRepository,
    EvidenceRequirementSetRepository,
    EvidenceSufficiencyRepository,
)
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.canonical.errors import NotFoundError
from app.utils.canonical_enums import (
    EvidenceRequirementSufficiency,
    EvidenceSufficiencyOutcome,
    EvidenceValidationOutcome,
    RequiredEvidenceState,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now

# Validation methods that always require a human sign-off, regardless of the
# collected evidence. Kept explicit and case-insensitive.
_MANUAL_VALIDATION_METHODS = frozenset({"manual_review", "manual_approval"})

# Validation outcomes that make a requirement STALE rather than INVALID.
_STALE_OUTCOMES = frozenset({EvidenceValidationOutcome.STALE.value})

# Validation outcomes that mean the requirement could not be evaluated.
_NOT_EVALUABLE_OUTCOMES = frozenset(
    {EvidenceValidationOutcome.INDETERMINATE.value}
)

# Evidence-requirement states that participate in sufficiency evaluation.
_EVALUATED_STATES = frozenset(
    {
        RequiredEvidenceState.REQUIRED.value,
        RequiredEvidenceState.OPTIONAL.value,
        RequiredEvidenceState.CONDITIONAL.value,
    }
)


def _load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def _requirement_status(
    *,
    state: str,
    manual: bool,
    cardinality: int,
    satisfied_count: int,
    invalid_outcomes: list[str],
) -> tuple[str, list[str]]:
    """Derive a single requirement's sufficiency status deterministically."""
    if state == RequiredEvidenceState.UNRESOLVED.value:
        return (
            EvidenceRequirementSufficiency.NOT_EVALUABLE.value,
            ["EVIDENCE_REQUIREMENT_UNRESOLVED_BASIS"],
        )
    if manual:
        return (
            EvidenceRequirementSufficiency.MANUAL_REVIEW_REQUIRED.value,
            ["EVIDENCE_REQUIREMENT_MANUAL_REVIEW_REQUIRED"],
        )
    if satisfied_count >= cardinality and cardinality >= 0 and satisfied_count > 0:
        return (
            EvidenceRequirementSufficiency.SATISFIED.value,
            ["EVIDENCE_REQUIREMENT_SATISFIED"],
        )
    if cardinality == 0 and satisfied_count == 0:
        # A zero-cardinality requirement is satisfied by the absence of a
        # disqualifying item; there is nothing to collect.
        return (
            EvidenceRequirementSufficiency.SATISFIED.value,
            ["EVIDENCE_REQUIREMENT_SATISFIED_ZERO_CARDINALITY"],
        )
    if satisfied_count > 0:
        return (
            EvidenceRequirementSufficiency.PARTIAL.value,
            ["EVIDENCE_REQUIREMENT_PARTIAL_CARDINALITY"],
        )
    # No valid normalized evidence — classify by the failing validations.
    if any(o in _NOT_EVALUABLE_OUTCOMES for o in invalid_outcomes):
        return (
            EvidenceRequirementSufficiency.NOT_EVALUABLE.value,
            ["EVIDENCE_REQUIREMENT_INDETERMINATE_VALIDATION"],
        )
    if any(o in _STALE_OUTCOMES for o in invalid_outcomes):
        return (
            EvidenceRequirementSufficiency.STALE.value,
            ["EVIDENCE_REQUIREMENT_STALE"],
        )
    if invalid_outcomes:
        return (
            EvidenceRequirementSufficiency.INVALID.value,
            ["EVIDENCE_REQUIREMENT_INVALID"]
            + [f"VALIDATION:{o}" for o in sorted(set(invalid_outcomes))],
        )
    return (
        EvidenceRequirementSufficiency.MISSING.value,
        ["EVIDENCE_REQUIREMENT_MISSING"],
    )


def _overall_outcome(mandatory_statuses: list[str]) -> tuple[str, list[str]]:
    """Aggregate the mandatory requirement statuses into the overall outcome.

    ``SUFFICIENT`` is only produced when every mandatory requirement is
    ``SATISFIED``. The precedence is deliberately conservative (fail-closed):
    ``MANUAL_REVIEW_REQUIRED`` > ``NOT_EVALUABLE`` > ``INSUFFICIENT`` >
    ``PARTIAL`` > ``SUFFICIENT``.
    """
    if not mandatory_statuses:
        return (
            EvidenceSufficiencyOutcome.SUFFICIENT.value,
            ["EVIDENCE_SUFFICIENT_NO_MANDATORY_REQUIREMENTS"],
        )
    S = EvidenceRequirementSufficiency
    if S.MANUAL_REVIEW_REQUIRED.value in mandatory_statuses:
        return (
            EvidenceSufficiencyOutcome.MANUAL_REVIEW_REQUIRED.value,
            ["EVIDENCE_MANUAL_REVIEW_REQUIRED"],
        )
    if S.NOT_EVALUABLE.value in mandatory_statuses:
        return (
            EvidenceSufficiencyOutcome.NOT_EVALUABLE.value,
            ["EVIDENCE_NOT_EVALUABLE_MANDATORY_REQUIREMENT"],
        )
    if any(
        status in (S.MISSING.value, S.INVALID.value, S.STALE.value)
        for status in mandatory_statuses
    ):
        return (
            EvidenceSufficiencyOutcome.INSUFFICIENT.value,
            ["EVIDENCE_INSUFFICIENT_MANDATORY_REQUIREMENT"],
        )
    if S.PARTIAL.value in mandatory_statuses:
        return (
            EvidenceSufficiencyOutcome.PARTIAL.value,
            ["EVIDENCE_PARTIAL_MANDATORY_REQUIREMENT"],
        )
    return (
        EvidenceSufficiencyOutcome.SUFFICIENT.value,
        ["EVIDENCE_SUFFICIENT_ALL_MANDATORY_SATISFIED"],
    )


def evaluate_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> EvidenceSufficiency:
    """Evaluate evidence sufficiency for a resolution and persist the record.

    Always persists a fresh, immutable record (like Decision/Assessment) --
    callers that want to reuse an up-to-date existing record instead should
    use :func:`evaluate_or_get_for_resolution`.
    """
    org = organization_id
    package = CanonicalEvidencePackageRepository(db).latest_for_evaluation(
        org, policy_resolution_id
    )
    if package is None:
        raise NotFoundError(
            "CanonicalEvidencePackage not found for evaluation: "
            f"{policy_resolution_id}"
        )

    evidence_set = None
    if package.evidence_requirement_set_id:
        evidence_set = EvidenceRequirementSetRepository(db).get(
            org, package.evidence_requirement_set_id
        )
    if evidence_set is None:
        evidence_set = EvidenceRequirementSetRepository(db).latest_for_resolution(
            org, policy_resolution_id
        )
    requirements = _load(evidence_set.evidence_requirements, []) if evidence_set else []

    # Valid normalized evidence grouped by requirement.
    normalized_refs = _load(package.normalized_evidence_references, []) or []
    satisfied_by_req: dict[str, int] = {}
    normalized_ids_by_req: dict[str, list[str]] = {}
    for ref in normalized_refs:
        if not isinstance(ref, dict):
            continue
        req_id = ref.get("evidence_requirement_id")
        if not req_id:
            continue
        if ref.get("validation_status") == EvidenceValidationOutcome.VALID.value:
            satisfied_by_req[req_id] = satisfied_by_req.get(req_id, 0) + 1
        normalized_ids_by_req.setdefault(req_id, []).append(
            ref.get("normalized_evidence_id")
        )

    # Failing validation outcomes grouped by requirement.
    invalid_by_req: dict[str, list[str]] = {}
    for item in _load(package.invalid_evidence, []) or []:
        if not isinstance(item, dict):
            continue
        req_id = item.get("evidence_requirement_id")
        if not req_id:
            continue
        invalid_by_req.setdefault(req_id, []).append(item.get("outcome"))

    requirement_results: list[dict[str, Any]] = []
    mandatory_statuses: list[str] = []

    for req in requirements:
        if not isinstance(req, dict):
            continue
        state = req.get("state")
        if state not in _EVALUATED_STATES and state != RequiredEvidenceState.UNRESOLVED.value:
            # NOT_REQUIRED items do not participate in sufficiency.
            continue
        req_id = req.get("evidence_requirement_id")
        mandatory = bool(req.get("mandatory", True))
        cardinality = int(req.get("cardinality", 1) or 0)
        validation_method = (req.get("validation_method") or "").lower()
        manual = validation_method in _MANUAL_VALIDATION_METHODS
        satisfied_count = satisfied_by_req.get(req_id, 0)
        invalid_outcomes = [o for o in invalid_by_req.get(req_id, []) if o]

        status, reason_codes = _requirement_status(
            state=state,
            manual=manual,
            cardinality=cardinality,
            satisfied_count=satisfied_count,
            invalid_outcomes=invalid_outcomes,
        )

        sufficiency_input = {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "evidence_requirement_id": req_id,
            "state": state,
            "mandatory": mandatory,
            "cardinality": cardinality,
            "validation_method": validation_method,
            "satisfied_count": satisfied_count,
            "invalid_outcomes": sorted(invalid_outcomes),
            "status": status,
        }
        entry = {
            "evidence_requirement_id": req_id,
            "control_ids": list(req.get("control_ids") or []),
            "requirement_ids": list(req.get("requirement_ids") or []),
            "state": state,
            "mandatory": mandatory,
            "cardinality": cardinality,
            "validation_method": req.get("validation_method"),
            "satisfied_count": satisfied_count,
            "normalized_evidence_ids": [
                nid for nid in normalized_ids_by_req.get(req_id, []) if nid
            ],
            "validation_outcomes": sorted(invalid_outcomes),
            "status": status,
            "reason_codes": reason_codes,
            "sufficiency_hash": hash_dict(sufficiency_input),
        }
        requirement_results.append(entry)
        if mandatory:
            mandatory_statuses.append(status)

    requirement_results.sort(
        key=lambda e: (e["evidence_requirement_id"] or "")
    )

    overall_result, overall_reasons = _overall_outcome(mandatory_statuses)
    reason_codes = ["EVIDENCE_SUFFICIENCY_EVALUATED"] + overall_reasons

    input_hash = hash_dict(
        {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "organization_id": org,
            "policy_resolution_id": policy_resolution_id,
            "canonical_evidence_package_id": package.id,
            "canonical_evidence_package_hash": package.package_hash,
            "evidence_requirement_set_id": (
                evidence_set.id if evidence_set else None
            ),
            "evidence_requirement_set_result_hash": (
                evidence_set.result_hash if evidence_set else None
            ),
        }
    )
    result_hash = hash_dict(
        {
            "input_hash": input_hash,
            "requirement_results": requirement_results,
            "overall_result": overall_result,
            "reason_codes": reason_codes,
        }
    )

    obj = EvidenceSufficiency(
        organization_id=org,
        evaluation_id=policy_resolution_id,
        policy_resolution_id=policy_resolution_id,
        evidence_requirement_set_id=(
            evidence_set.id if evidence_set else None
        ),
        canonical_evidence_package_id=package.id,
        collection_job_id=package.collection_job_id,
        requirement_results=json.dumps(requirement_results),
        overall_result=overall_result,
        reason_codes=json.dumps(reason_codes),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=input_hash,
        result_hash=result_hash,
        evaluated_at=utc_now(),
    )
    return EvidenceSufficiencyRepository(db).add(obj)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[EvidenceSufficiency]:
    return EvidenceSufficiencyRepository(db).get(organization_id, resource_id)


def latest_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> Optional[EvidenceSufficiency]:
    return EvidenceSufficiencyRepository(db).latest_for_resolution(
        organization_id, policy_resolution_id
    )


def evaluate_or_get_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> EvidenceSufficiency:
    """Return the sufficiency record for a resolution, (re)computing it if stale
    or absent.

    Reuses the latest persisted record only when its ``input_hash`` still
    matches the *current* evidence package + evidence requirement set
    (cheap "latest" lookups, no full sufficiency evaluation performed) —
    never on "a record merely exists". A second, more-complete evidence
    collection produces a new CanonicalEvidencePackage, which must trigger a
    fresh evaluation rather than reusing a record computed from the earlier,
    incomplete package.
    """
    org = organization_id
    existing = latest_for_resolution(db, org, policy_resolution_id)
    if existing is not None:
        package = CanonicalEvidencePackageRepository(db).latest_for_evaluation(
            org, policy_resolution_id
        )
        if package is not None:
            evidence_set = None
            if package.evidence_requirement_set_id:
                evidence_set = EvidenceRequirementSetRepository(db).get(
                    org, package.evidence_requirement_set_id
                )
            if evidence_set is None:
                evidence_set = EvidenceRequirementSetRepository(
                    db
                ).latest_for_resolution(org, policy_resolution_id)
            current_hash = hash_dict(
                {
                    "engine_version": DETERMINISTIC_ENGINE_VERSION,
                    "organization_id": org,
                    "policy_resolution_id": policy_resolution_id,
                    "canonical_evidence_package_id": package.id,
                    "canonical_evidence_package_hash": package.package_hash,
                    "evidence_requirement_set_id": (
                        evidence_set.id if evidence_set else None
                    ),
                    "evidence_requirement_set_result_hash": (
                        evidence_set.result_hash if evidence_set else None
                    ),
                }
            )
            if existing.input_hash == current_hash:
                return existing
    return evaluate_for_resolution(db, organization_id, policy_resolution_id)


def list_(
    db: Session,
    organization_id: str,
    *,
    policy_resolution_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[EvidenceSufficiency]:
    repo = EvidenceSufficiencyRepository(db)
    if policy_resolution_id is not None:
        return repo.list_for_resolution(
            organization_id, policy_resolution_id, skip=skip, limit=limit
        )
    return repo.list(organization_id, skip=skip, limit=limit)
