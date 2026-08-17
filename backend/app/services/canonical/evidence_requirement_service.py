"""Evidence Requirement Resolution service — deterministic runtime stage #4.

Evidence Requirement Resolution runs **after** Control Determination and
**before** evidence collection. For a completed :class:`PolicyResolution` it
consumes the :class:`ApplicableControlSet` and:

1. resolves the evidence needed by every applicable control,
2. deduplicates evidence requirements shared across controls,
3. preserves the mappings between evidence requirements, controls and
   requirements,
4. defines, for each evidence requirement, the required evidence type, subject,
   target, allowed source type, allowed issuer, freshness threshold,
   validation method, cardinality and mandatory status,
5. assigns each evidence requirement a deterministic state — ``REQUIRED``,
   ``OPTIONAL``, ``CONDITIONAL``, ``NOT_REQUIRED`` or ``UNRESOLVED``,
6. produces a persistent :class:`EvidenceRequirementSet`.

When the applicability basis for the controls that need an evidence item is
missing or indeterminate the item resolves to ``UNRESOLVED`` — a missing basis
can never silently produce success.

No LLM and no dynamic code execution is used anywhere in this module.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.evidence_requirement_set import EvidenceRequirementSet
from app.repositories.canonical import (
    EvidenceRequirementSetRepository,
    ExecutableGovernancePackageRepository,
    PolicyResolutionRepository,
)
from app.schemas.canonical.control_evidence import (
    EvidenceRequirementResolutionCreate,
)
from app.services.canonical import control_determination_service
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.canonical.errors import NotFoundError
from app.utils.canonical_enums import (
    ControlDeterminationStatus,
    RequiredEvidenceState,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def _load(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _evidence_state(
    statuses: list[str], mandatory: bool, has_referencing_control: bool
) -> tuple[str, list[str]]:
    """Derive an evidence requirement's state from its controls' statuses.

    ``statuses`` are the determination statuses of the *included* controls that
    reference the evidence item. ``has_referencing_control`` is true when at
    least one control (included or excluded) references it.
    """
    if ControlDeterminationStatus.APPLICABLE.value in statuses:
        if mandatory:
            return (
                RequiredEvidenceState.REQUIRED.value,
                ["EVIDENCE_REQUIRED_BY_APPLICABLE_CONTROL"],
            )
        return (
            RequiredEvidenceState.OPTIONAL.value,
            ["EVIDENCE_OPTIONAL_FOR_APPLICABLE_CONTROL"],
        )
    if ControlDeterminationStatus.CONDITIONAL.value in statuses:
        return (
            RequiredEvidenceState.CONDITIONAL.value,
            ["EVIDENCE_CONDITIONAL_ON_CONTROL_CONDITION"],
        )
    if ControlDeterminationStatus.INDETERMINATE.value in statuses:
        return (
            RequiredEvidenceState.UNRESOLVED.value,
            ["EVIDENCE_UNRESOLVED_INDETERMINATE_BASIS"],
        )
    # Only excluded (NOT_APPLICABLE) controls reference it.
    if has_referencing_control:
        return (
            RequiredEvidenceState.NOT_REQUIRED.value,
            ["EVIDENCE_NOT_REQUIRED_CONTROL_NOT_APPLICABLE"],
        )
    return (
        RequiredEvidenceState.NOT_REQUIRED.value,
        ["EVIDENCE_NOT_REQUIRED_UNREFERENCED"],
    )


def resolve_for_resolution(
    db: Session, payload: EvidenceRequirementResolutionCreate
) -> EvidenceRequirementSet:
    """Resolve the evidence requirements for a resolution and persist the set.

    Always persists a fresh, immutable record (like Decision/Assessment) --
    callers that want to reuse an up-to-date existing record instead should
    use :func:`resolve_or_get_for_resolution`.
    """
    org = payload.organization_id
    resolution = PolicyResolutionRepository(db).get(
        org, payload.policy_resolution_id
    )
    if resolution is None:
        raise NotFoundError(
            f"PolicyResolution not found: {payload.policy_resolution_id}"
        )

    # Control Determination is the sole authority for which controls apply; the
    # set is computed on demand when it has not been produced yet.
    control_set = control_determination_service.determine_or_get_for_resolution(
        db, org, resolution.id
    )
    controls = _load(control_set.controls) or []

    # Included controls keyed by (package_id, control_id).
    included: dict[tuple[str, str], dict[str, Any]] = {}
    for ctrl in controls:
        if not isinstance(ctrl, dict):
            continue
        pkg_id = ctrl.get("package_id")
        control_id = ctrl.get("control_id")
        if pkg_id and control_id:
            included[(pkg_id, control_id)] = ctrl

    selected_packages = _load(resolution.selected_packages) or []
    pkg_repo = ExecutableGovernancePackageRepository(db)

    evidence_out: list[dict[str, Any]] = []
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

        control_defs = {
            c.get("control_id"): c
            for c in (_load(package.control_definitions) or [])
            if isinstance(c, dict) and c.get("control_id")
        }

        for ev in _load(package.evidence_requirements) or []:
            if not isinstance(ev, dict):
                continue
            evidence_id = ev.get("evidence_requirement_id")
            if not evidence_id:
                continue
            key = (package_id, evidence_id)
            if key in seen:
                continue  # deduplicate shared evidence requirements
            seen.add(key)

            # Every control that references this evidence item — declared both
            # via the evidence definition's control_ids and via a control's
            # evidence_requirement_ids (kept in sync, deduplicated here).
            referencing_control_ids: set[str] = {
                cid for cid in (ev.get("control_ids") or []) if cid
            }
            for cid, cdef in control_defs.items():
                if evidence_id in (cdef.get("evidence_requirement_ids") or []):
                    referencing_control_ids.add(cid)

            included_refs = [
                included[(package_id, cid)]
                for cid in sorted(referencing_control_ids)
                if (package_id, cid) in included
            ]
            statuses = [ctrl["status"] for ctrl in included_refs]
            mandatory = bool(ev.get("mandatory", True))

            state, reason_codes = _evidence_state(
                statuses, mandatory, bool(referencing_control_ids)
            )

            if included_refs:
                control_ids = sorted(
                    {ctrl["control_id"] for ctrl in included_refs}
                )
                applicable_control_ids = sorted(
                    {ctrl["applicable_control_id"] for ctrl in included_refs}
                )
                requirement_ids = sorted(
                    {
                        rid
                        for ctrl in included_refs
                        for rid in ctrl.get("requirement_ids", [])
                    }
                )
            else:
                control_ids = sorted(referencing_control_ids)
                applicable_control_ids = []
                requirement_ids = sorted(
                    {
                        rid
                        for cid in referencing_control_ids
                        for rid in (
                            control_defs.get(cid, {}).get("requirement_ids") or []
                        )
                    }
                )

            resolution_input = {
                "engine_version": DETERMINISTIC_ENGINE_VERSION,
                "policy_resolution_id": resolution.id,
                "package_id": package_id,
                "package_version": package_version,
                "evidence_requirement_id": evidence_id,
                "control_ids": control_ids,
                "control_statuses": sorted(statuses),
                "mandatory": mandatory,
                "state": state,
            }
            resolution_hash = hash_dict(resolution_input)

            evidence_out.append(
                {
                    "evidence_requirement_id": evidence_id,
                    "control_ids": control_ids,
                    "applicable_control_ids": applicable_control_ids,
                    "requirement_ids": requirement_ids,
                    "package_id": package_id,
                    "package_version": package_version,
                    "governance_packages": [
                        {
                            "package_id": package_id,
                            "package_version": package_version,
                        }
                    ],
                    "evidence_type": ev.get("evidence_type"),
                    "subject": ev.get("subject_binding"),
                    "target": ev.get("target_binding"),
                    "allowed_source_type": ev.get("authoritative_source_type"),
                    "allowed_issuers": list(ev.get("allowed_issuers") or []),
                    "freshness_threshold": ev.get("freshness_requirement"),
                    "validation_method": ev.get("validation_method"),
                    "cardinality": int(ev.get("minimum_cardinality", 1)),
                    "mandatory": mandatory,
                    "state": state,
                    "resolution_reason": reason_codes,
                    "resolution_hash": resolution_hash,
                }
            )

    evidence_out.sort(
        key=lambda e: (e["package_id"], e["evidence_requirement_id"])
    )

    reason_codes: list[str] = ["EVIDENCE_REQUIREMENTS_RESOLVED"]
    if any(
        e["state"] == RequiredEvidenceState.UNRESOLVED.value for e in evidence_out
    ):
        reason_codes.append("EVIDENCE_UNRESOLVED_PRESENT")
    if not evidence_out:
        reason_codes.append("NO_EVIDENCE_REQUIREMENTS")

    input_hash = hash_dict(
        {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "organization_id": org,
            "policy_resolution_id": resolution.id,
            "applicable_control_set_id": control_set.id,
            "applicable_control_set_result_hash": control_set.result_hash,
        }
    )
    result_hash = hash_dict(
        {
            "input_hash": input_hash,
            "evidence_requirements": evidence_out,
            "reason_codes": reason_codes,
        }
    )

    obj = EvidenceRequirementSet(
        organization_id=org,
        policy_resolution_id=resolution.id,
        applicable_control_set_id=control_set.id,
        actor_identity_id=resolution.actor_identity_id,
        intent_id=resolution.intent_id,
        target_id=resolution.target_id,
        operational_context_id=resolution.operational_context_id,
        evidence_requirements=json.dumps(evidence_out),
        reason_codes=json.dumps(reason_codes),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=input_hash,
        result_hash=result_hash,
        resolved_at=utc_now(),
    )
    return EvidenceRequirementSetRepository(db).add(obj)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[EvidenceRequirementSet]:
    return EvidenceRequirementSetRepository(db).get(organization_id, resource_id)


def get_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> Optional[EvidenceRequirementSet]:
    """Return the most recent evidence set for a resolution, if any."""
    return EvidenceRequirementSetRepository(db).latest_for_resolution(
        organization_id, policy_resolution_id
    )


def resolve_or_get_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> EvidenceRequirementSet:
    """Return the evidence set for a resolution, (re)computing it if stale or absent.

    Reuses the latest persisted record only when its ``input_hash`` still
    matches the *current* control set (control_determination_service's own
    ``determine_or_get_for_resolution`` is itself cheap once up to date, so
    this precheck costs little) — never on "a record merely exists".
    """
    resolution = PolicyResolutionRepository(db).get(
        organization_id, policy_resolution_id
    )
    if resolution is not None:
        existing = EvidenceRequirementSetRepository(db).latest_for_resolution(
            organization_id, resolution.id
        )
        if existing is not None:
            control_set = (
                control_determination_service.determine_or_get_for_resolution(
                    db, organization_id, resolution.id
                )
            )
            current_hash = hash_dict(
                {
                    "engine_version": DETERMINISTIC_ENGINE_VERSION,
                    "organization_id": organization_id,
                    "policy_resolution_id": resolution.id,
                    "applicable_control_set_id": control_set.id,
                    "applicable_control_set_result_hash": control_set.result_hash,
                }
            )
            if existing.input_hash == current_hash:
                return existing
    return resolve_for_resolution(
        db,
        EvidenceRequirementResolutionCreate(
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
) -> Sequence[EvidenceRequirementSet]:
    repo = EvidenceRequirementSetRepository(db)
    if policy_resolution_id is not None:
        return repo.list_for_resolution(
            organization_id, policy_resolution_id, skip=skip, limit=limit
        )
    return repo.list(organization_id, skip=skip, limit=limit)
