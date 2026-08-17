"""Control Determination service — deterministic runtime stage #3.

Control Determination runs **after** Applicability Evaluation and **before**
evidence collection and the decision engine. It never decides the final
outcome; it only determines *which controls apply* to the governed tuple, and
does so deterministically from published governance packages — controls are no
longer embedded as hard-coded ``if`` statements in the decision engine.

For a completed :class:`PolicyResolution` it:

1. selects the controls mapped to ``APPLICABLE`` or conditionally applicable
   requirements,
2. excludes controls whose requirements are all ``NOT_APPLICABLE``,
3. preserves ``CONDITIONAL`` and ``INDETERMINATE`` status — a missing
   applicability basis surfaces as ``INDETERMINATE`` and is never silently
   collapsed to ``NOT_APPLICABLE``,
4. deduplicates controls shared across requirements,
5. resolves each control's priority and mandatory status,
6. records the exact governing package ids + versions and the requirement ids
   each control is traceable to,
7. produces a persistent :class:`ApplicableControlSet`.

No LLM and no dynamic code execution is used anywhere in this module — every
step is deterministic and reproducible via the recorded hashes.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.applicable_control_set import ApplicableControlSet
from app.repositories.canonical import (
    ApplicabilityEvaluationRepository,
    ApplicableControlSetRepository,
    ExecutableGovernancePackageRepository,
    PolicyResolutionRepository,
)
from app.schemas.canonical.control_evidence import ControlDeterminationCreate
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.canonical.errors import NotFoundError
from app.utils.canonical_enums import (
    ApplicabilityResult,
    ControlDeterminationStatus,
    ControlFailureDisposition,
    GovernanceSeverity,
)
from app.utils.hashing import hash_dict, sha256_hash
from app.utils.timestamps import utc_now


def _load(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _control_status(
    statuses: list[str], missing: list[str]
) -> tuple[Optional[str], list[str]]:
    """Derive a control's determination status from its requirements' results.

    Returns ``(status, reason_codes)``. ``status`` is ``None`` when the control
    must be *excluded* (all mapped requirements are ``NOT_APPLICABLE``).
    """
    if ApplicabilityResult.APPLICABLE.value in statuses:
        return (
            ControlDeterminationStatus.APPLICABLE.value,
            ["CONTROL_SELECTED_APPLICABLE"],
        )
    if ApplicabilityResult.CONDITIONAL.value in statuses:
        return (
            ControlDeterminationStatus.CONDITIONAL.value,
            ["CONTROL_SELECTED_CONDITIONAL"],
        )
    if ApplicabilityResult.INDETERMINATE.value in statuses:
        return (
            ControlDeterminationStatus.INDETERMINATE.value,
            ["CONTROL_INDETERMINATE_BASIS"],
        )
    if missing:
        # No applicability basis for the mapped requirements — never silently
        # treat as NOT_APPLICABLE.
        return (
            ControlDeterminationStatus.INDETERMINATE.value,
            ["CONTROL_MISSING_APPLICABILITY_BASIS"]
            + [f"MISSING:{m}" for m in missing],
        )
    return None, []


def _expected_outcome(ctrl: dict[str, Any]) -> Any:
    if ctrl.get("expected_outcome") is not None:
        return ctrl.get("expected_outcome")
    impact = ctrl.get("decision_impact")
    if isinstance(impact, dict):
        return impact.get("expected_outcome")
    return None


def _applicable_control_id(
    policy_resolution_id: str, package_id: str, control_id: str
) -> str:
    digest = sha256_hash(f"{policy_resolution_id}|{package_id}|{control_id}")
    return f"acs-{digest[:24]}"


def _current_applicability_input_hash(
    db: Session, org: str, resolution: PolicyResolution
) -> tuple[str, dict[tuple[str, str], str], list]:
    """Compute the input_hash a fresh determination would use right now.

    Derived solely from the current applicability results for this
    resolution -- cheap (a couple of DB reads + hashing), no control
    determination performed. Shared by :func:`determine_for_resolution` (as
    its actual ``input_hash``) and :func:`determine_or_get_for_resolution`
    (as a freshness check before deciding whether to reuse the latest
    persisted record) so the two can never drift out of sync.
    """
    evaluations = ApplicabilityEvaluationRepository(db).list_for_resolution(
        org, resolution.id, limit=10000
    )
    result_map: dict[tuple[str, str], str] = {
        (e.package_id, e.requirement_id): e.result for e in evaluations
    }
    input_hash = hash_dict(
        {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "organization_id": org,
            "policy_resolution_id": resolution.id,
            "policy_resolution_result_hash": resolution.result_hash,
            "requirement_results": sorted(
                [
                    {
                        "package_id": pkg_id,
                        "requirement_id": rid,
                        "result": result,
                    }
                    for (pkg_id, rid), result in result_map.items()
                ],
                key=lambda entry: (entry["package_id"], entry["requirement_id"]),
            ),
        }
    )
    return input_hash, result_map, evaluations


def determine_for_resolution(
    db: Session, payload: ControlDeterminationCreate
) -> ApplicableControlSet:
    """Determine the applicable controls for a resolution and persist the set.

    Always persists a fresh, immutable record (like Decision/Assessment) --
    callers that want to reuse an up-to-date existing record instead should
    use :func:`determine_or_get_for_resolution`.
    """
    org = payload.organization_id
    resolution = PolicyResolutionRepository(db).get(
        org, payload.policy_resolution_id
    )
    if resolution is None:
        raise NotFoundError(
            f"PolicyResolution not found: {payload.policy_resolution_id}"
        )

    input_hash, result_map, evaluations = _current_applicability_input_hash(
        db, org, resolution
    )

    selected_packages = _load(resolution.selected_packages) or []
    pkg_repo = ExecutableGovernancePackageRepository(db)

    controls_out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for selected in selected_packages:
        if not isinstance(selected, dict):
            continue
        package_id = selected.get("package_id")
        package_version = selected.get("package_version")
        if not package_id:
            continue
        package = pkg_repo.get(org, package_id)
        if package is None:
            continue
        for ctrl in _load(package.control_definitions) or []:
            if not isinstance(ctrl, dict):
                continue
            control_id = ctrl.get("control_id")
            if not control_id:
                continue
            key = (package_id, control_id)
            if key in seen:
                continue  # deduplicate shared controls

            requirement_ids = [
                rid for rid in (ctrl.get("requirement_ids") or []) if rid
            ]
            statuses: list[str] = []
            missing: list[str] = []
            for rid in requirement_ids:
                res = result_map.get((package_id, rid))
                if res is None:
                    missing.append(rid)
                else:
                    statuses.append(res)

            status, reason_codes = _control_status(statuses, missing)
            if status is None:
                continue  # excluded: all mapped requirements NOT_APPLICABLE

            seen.add(key)

            governance_packages = [
                {"package_id": package_id, "package_version": package_version}
            ]
            determination_input = {
                "engine_version": DETERMINISTIC_ENGINE_VERSION,
                "policy_resolution_id": resolution.id,
                "package_id": package_id,
                "package_version": package_version,
                "control_id": control_id,
                "requirement_ids": requirement_ids,
                "requirement_results": sorted(
                    [
                        {"requirement_id": rid, "result": result_map[(package_id, rid)]}
                        for rid in requirement_ids
                        if (package_id, rid) in result_map
                    ],
                    key=lambda entry: entry["requirement_id"],
                ),
                "status": status,
            }
            determination_hash = hash_dict(determination_input)

            controls_out.append(
                {
                    "applicable_control_id": _applicable_control_id(
                        resolution.id, package_id, control_id
                    ),
                    "control_id": control_id,
                    "requirement_ids": sorted(set(requirement_ids)),
                    "package_id": package_id,
                    "package_version": package_version,
                    "governance_packages": governance_packages,
                    "control_objective": ctrl.get("control_objective"),
                    "mandatory": bool(ctrl.get("mandatory", True)),
                    "severity": ctrl.get("severity")
                    or GovernanceSeverity.MEDIUM.value,
                    "evaluation_expression": ctrl.get("evaluation_expression"),
                    "expected_outcome": _expected_outcome(ctrl),
                    "failure_disposition": ctrl.get("failure_disposition")
                    or ControlFailureDisposition.DENY.value,
                    "remediation_eligible": bool(
                        ctrl.get("remediation_eligible", False)
                    ),
                    "evidence_requirement_ids": list(
                        ctrl.get("evidence_requirement_ids") or []
                    ),
                    "status": status,
                    "determination_reason": reason_codes,
                    "determination_hash": determination_hash,
                }
            )

    controls_out.sort(key=lambda c: (c["package_id"], c["control_id"]))

    reason_codes: list[str] = ["CONTROLS_DETERMINED"]
    if not evaluations:
        reason_codes.append("NO_APPLICABILITY_BASIS")
    if not controls_out:
        reason_codes.append("NO_CONTROLS_SELECTED")

    result_hash = hash_dict(
        {
            "input_hash": input_hash,
            "controls": controls_out,
            "reason_codes": reason_codes,
        }
    )

    obj = ApplicableControlSet(
        organization_id=org,
        policy_resolution_id=resolution.id,
        actor_identity_id=resolution.actor_identity_id,
        intent_id=resolution.intent_id,
        target_id=resolution.target_id,
        operational_context_id=resolution.operational_context_id,
        controls=json.dumps(controls_out),
        reason_codes=json.dumps(reason_codes),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=input_hash,
        result_hash=result_hash,
        determined_at=utc_now(),
    )
    return ApplicableControlSetRepository(db).add(obj)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[ApplicableControlSet]:
    return ApplicableControlSetRepository(db).get(organization_id, resource_id)


def get_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> Optional[ApplicableControlSet]:
    """Return the most recent control set for a resolution, if any."""
    return ApplicableControlSetRepository(db).latest_for_resolution(
        organization_id, policy_resolution_id
    )


def determine_or_get_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> ApplicableControlSet:
    """Return the control set for a resolution, (re)computing it if stale or absent.

    Reuses the latest persisted record only when its ``input_hash`` still
    matches the *current* applicability results (checked cheaply, without
    running full control determination) — never on "a record merely
    exists". A record computed from an incomplete or stale applicability
    basis must be recomputed once that basis improves, not reused forever.
    """
    resolution = PolicyResolutionRepository(db).get(
        organization_id, policy_resolution_id
    )
    if resolution is not None:
        existing = ApplicableControlSetRepository(db).latest_for_resolution(
            organization_id, resolution.id
        )
        if existing is not None:
            current_hash, _, _ = _current_applicability_input_hash(
                db, organization_id, resolution
            )
            if existing.input_hash == current_hash:
                return existing
    return determine_for_resolution(
        db,
        ControlDeterminationCreate(
            organization_id=organization_id,
            policy_resolution_id=policy_resolution_id,
        ),
    )


def list_(
    db: Session,
    organization_id: str,
    *,
    policy_resolution_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[ApplicableControlSet]:
    repo = ApplicableControlSetRepository(db)
    if policy_resolution_id is not None:
        return repo.list_for_resolution(
            organization_id, policy_resolution_id, skip=skip, limit=limit
        )
    return repo.list(organization_id, skip=skip, limit=limit)
