"""Control Evaluation service — deterministic runtime stage.

Control Evaluation runs **after** Evidence Sufficiency and **before**
Assessment. It formally evaluates each :class:`ApplicableControl` and produces
exactly **one immutable** :class:`ControlEvaluation` per control.

Every control is evaluated using:

* **normalized evidence only** — the facts available to the expression engine are
  drawn solely from :class:`NormalizedEvidence`; raw intent assertions are never
  in scope, so a control can never be satisfied without normalized validated
  evidence,
* the approved deterministic expression engine (no ``eval``/``exec``),
* the exact control version and the exact governance package version.

Each control's verdict is one of ``SATISFIED``, ``NOT_SATISFIED``,
``NOT_EVALUABLE`` or ``MANUAL_REVIEW_REQUIRED``:

1. the control's evidence requirements are gated on the Evidence Sufficiency
   result first — insufficient / manual / stale evidence short-circuits the
   verdict before any expression is evaluated,
2. only when the mandatory evidence is ``SATISFIED`` is the control expression
   evaluated against the normalized evidence facts.

No LLM is used for any verdict; every step is deterministic and reproducible via
the recorded hashes.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.control_evaluation import ControlEvaluation
from app.repositories.canonical import (
    CanonicalEvidencePackageRepository,
    ControlEvaluationRepository,
    ApplicableControlSetRepository,
    EvidenceRequirementSetRepository,
    NormalizedEvidenceRepository,
)
from app.services.canonical import evidence_sufficiency_service
from app.services.canonical.control_determination_service import (
    determine_or_get_for_resolution,
)
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.canonical.errors import NotFoundError
from app.services.canonical.package_interpreter import evaluate_expression
from app.utils.canonical_enums import (
    ControlEvaluationOutcome,
    EvidenceRequirementSufficiency,
    GovernanceSeverity,
)
from app.utils.hashing import hash_dict, sha256_hash
from app.utils.timestamps import utc_now


def _load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def _control_evaluation_id(
    policy_resolution_id: str, package_id: Optional[str], control_id: str
) -> str:
    digest = sha256_hash(
        f"{policy_resolution_id}|{package_id or ''}|{control_id}"
    )
    return f"ce-{digest[:24]}"


def _evidence_facts(
    normalized_by_req: dict[str, list[Any]]
) -> dict[str, Any]:
    """Build the deterministic fact namespace from normalized evidence only."""
    evidence: dict[str, Any] = {}
    for req_id, items in normalized_by_req.items():
        if not items:
            continue
        first = items[0]
        evidence[req_id] = {
            "present": True,
            "count": len(items),
            "claims": _load(first.normalized_claims, {}) or {},
            "subject": first.subject,
            "target": first.target,
            "issuer": first.issuer,
            "source": first.source,
            "type": first.evidence_type,
            "validation_status": first.validation_status,
        }
    return {"evidence": evidence}


def _gate_on_sufficiency(
    *,
    evidence_requirement_ids: list[str],
    suff_status: dict[str, str],
) -> tuple[Optional[str], list[str]]:
    """Gate a control on its evidence requirements' sufficiency statuses.

    Every evidence requirement declared on the control is needed by the control,
    so all of them are considered here (independently of the evidence-level
    mandatory flag, which only governs overall evidence sufficiency). Returns
    ``(result, reason_codes)``; ``result`` is ``None`` when the evidence gate
    passes and the control expression should be evaluated.
    """
    S = EvidenceRequirementSufficiency
    statuses = [
        suff_status[rid]
        for rid in evidence_requirement_ids
        if rid in suff_status
    ]
    missing_sufficiency = [
        rid for rid in evidence_requirement_ids if rid not in suff_status
    ]

    if S.MANUAL_REVIEW_REQUIRED.value in statuses:
        return (
            ControlEvaluationOutcome.MANUAL_REVIEW_REQUIRED.value,
            ["CONTROL_MANUAL_REVIEW_REQUIRED"],
        )
    if missing_sufficiency:
        return (
            ControlEvaluationOutcome.NOT_EVALUABLE.value,
            ["CONTROL_MISSING_EVIDENCE_SUFFICIENCY"]
            + [f"MISSING:{rid}" for rid in sorted(missing_sufficiency)],
        )
    if any(
        status in (S.STALE.value, S.NOT_EVALUABLE.value) for status in statuses
    ):
        return (
            ControlEvaluationOutcome.NOT_EVALUABLE.value,
            ["CONTROL_EVIDENCE_NOT_EVALUABLE"],
        )
    if any(
        status in (S.MISSING.value, S.INVALID.value, S.PARTIAL.value)
        for status in statuses
    ):
        return (
            ControlEvaluationOutcome.NOT_SATISFIED.value,
            ["CONTROL_EVIDENCE_INSUFFICIENT"],
        )
    return None, []


def evaluate_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> list[ControlEvaluation]:
    """Evaluate every applicable control for a resolution and persist results."""
    org = organization_id

    control_set = ApplicableControlSetRepository(db).latest_for_resolution(
        org, policy_resolution_id
    )
    if control_set is None:
        control_set = determine_or_get_for_resolution(
            db, org, policy_resolution_id
        )
    controls = _load(control_set.controls, []) or []

    sufficiency = evidence_sufficiency_service.evaluate_or_get_for_resolution(
        db, org, policy_resolution_id
    )
    suff_status: dict[str, str] = {}
    for entry in _load(sufficiency.requirement_results, []) or []:
        if isinstance(entry, dict) and entry.get("evidence_requirement_id"):
            suff_status[entry["evidence_requirement_id"]] = entry.get("status")

    package = CanonicalEvidencePackageRepository(db).latest_for_evaluation(
        org, policy_resolution_id
    )

    evidence_set = None
    if package is not None and package.evidence_requirement_set_id:
        evidence_set = EvidenceRequirementSetRepository(db).get(
            org, package.evidence_requirement_set_id
        )
    if evidence_set is None:
        evidence_set = EvidenceRequirementSetRepository(db).latest_for_resolution(
            org, policy_resolution_id
        )
    req_mandatory: dict[str, bool] = {}
    if evidence_set is not None:
        for req in _load(evidence_set.evidence_requirements, []) or []:
            if isinstance(req, dict) and req.get("evidence_requirement_id"):
                req_mandatory[req["evidence_requirement_id"]] = bool(
                    req.get("mandatory", True)
                )

    # Normalized evidence (the only facts a control may use) grouped by req.
    normalized_by_req: dict[str, list[Any]] = {}
    normalized_ids_by_req: dict[str, list[str]] = {}
    if package is not None and package.collection_job_id:
        normalized = NormalizedEvidenceRepository(db).list_for_job(
            org, package.collection_job_id
        )
        for norm in normalized:
            normalized_by_req.setdefault(
                norm.evidence_requirement_id, []
            ).append(norm)
            normalized_ids_by_req.setdefault(
                norm.evidence_requirement_id, []
            ).append(norm.id)

    facts = _evidence_facts(normalized_by_req)

    results: list[ControlEvaluation] = []
    repo = ControlEvaluationRepository(db)

    for ctrl in sorted(
        (c for c in controls if isinstance(c, dict)),
        key=lambda c: (c.get("package_id") or "", c.get("control_id") or ""),
    ):
        control_id = ctrl.get("control_id")
        if not control_id:
            continue
        package_id = ctrl.get("package_id")
        package_version = ctrl.get("package_version")
        control_version = ctrl.get("control_version") or package_version
        evidence_requirement_ids = [
            rid for rid in (ctrl.get("evidence_requirement_ids") or []) if rid
        ]
        requirement_ids = list(ctrl.get("requirement_ids") or [])
        mandatory = bool(ctrl.get("mandatory", True))
        severity = ctrl.get("severity") or GovernanceSeverity.MEDIUM.value
        expression = ctrl.get("evaluation_expression")
        expected_value = ctrl.get("expected_value", True)

        evidence_references = sorted(
            {
                nid
                for rid in evidence_requirement_ids
                for nid in normalized_ids_by_req.get(rid, [])
            }
        )
        evidence_sufficiency_references = [
            {
                "evidence_requirement_id": rid,
                "status": suff_status.get(rid),
                "mandatory": req_mandatory.get(rid, True),
            }
            for rid in sorted(evidence_requirement_ids)
        ]

        gate_result, gate_reasons = _gate_on_sufficiency(
            evidence_requirement_ids=evidence_requirement_ids,
            suff_status=suff_status,
        )

        observed_value: Any = None
        if gate_result is not None:
            result = gate_result
            reason_codes = gate_reasons
        else:
            # Evidence is sufficient — evaluate the control expression against
            # the normalized evidence facts only.
            if not isinstance(expression, str) or not expression.strip():
                # No expression: the control is satisfied by its (sufficient)
                # normalized evidence alone.
                observed_value = True
                result = ControlEvaluationOutcome.SATISFIED.value
                reason_codes = ["CONTROL_SATISFIED_BY_EVIDENCE"]
            else:
                try:
                    observed_value = bool(
                        evaluate_expression(expression, facts)
                    )
                except Exception:  # noqa: BLE001 - fail-closed on any eval error
                    observed_value = None
                    result = ControlEvaluationOutcome.NOT_EVALUABLE.value
                    reason_codes = ["CONTROL_EXPRESSION_ERROR"]
                else:
                    if observed_value == bool(expected_value):
                        result = ControlEvaluationOutcome.SATISFIED.value
                        reason_codes = ["CONTROL_SATISFIED"]
                    else:
                        result = ControlEvaluationOutcome.NOT_SATISFIED.value
                        reason_codes = ["CONTROL_EXPRESSION_NOT_SATISFIED"]

        input_hash = hash_dict(
            {
                "engine_version": DETERMINISTIC_ENGINE_VERSION,
                "policy_resolution_id": policy_resolution_id,
                "package_id": package_id,
                "package_version": package_version,
                "control_id": control_id,
                "control_version": control_version,
                "evaluation_expression": expression,
                "expected_value": expected_value,
                "evidence_requirement_ids": sorted(evidence_requirement_ids),
                "evidence_sufficiency_references": evidence_sufficiency_references,
                "evidence_references": evidence_references,
                "facts": {
                    rid: facts["evidence"].get(rid)
                    for rid in sorted(evidence_requirement_ids)
                },
            }
        )
        result_hash = hash_dict(
            {
                "input_hash": input_hash,
                "result": result,
                "observed_value": observed_value,
                "reason_codes": reason_codes,
            }
        )

        obj = ControlEvaluation(
            organization_id=org,
            evaluation_id=policy_resolution_id,
            policy_resolution_id=policy_resolution_id,
            applicable_control_set_id=control_set.id,
            evidence_sufficiency_id=sufficiency.id,
            canonical_evidence_package_id=(
                package.id if package is not None else None
            ),
            control_evaluation_id=_control_evaluation_id(
                policy_resolution_id, package_id, control_id
            ),
            control_id=control_id,
            package_id=package_id,
            package_version=package_version,
            control_version=control_version,
            mandatory=mandatory,
            severity=severity,
            requirement_ids=json.dumps(requirement_ids),
            evidence_requirement_ids=json.dumps(evidence_requirement_ids),
            evidence_references=json.dumps(evidence_references),
            evidence_sufficiency_references=json.dumps(
                evidence_sufficiency_references
            ),
            evaluation_expression=(
                expression if isinstance(expression, str) else None
            ),
            expected_value=json.dumps(expected_value),
            observed_value=json.dumps(observed_value),
            result=result,
            reason_codes=json.dumps(reason_codes),
            engine_version=DETERMINISTIC_ENGINE_VERSION,
            input_hash=input_hash,
            result_hash=result_hash,
            evaluated_at=utc_now(),
        )
        results.append(repo.add(obj))

    return results


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[ControlEvaluation]:
    return ControlEvaluationRepository(db).get(organization_id, resource_id)


def list_for_resolution(
    db: Session,
    organization_id: str,
    policy_resolution_id: str,
    *,
    skip: int = 0,
    limit: int = 500,
) -> Sequence[ControlEvaluation]:
    return ControlEvaluationRepository(db).list_for_resolution(
        organization_id, policy_resolution_id, skip=skip, limit=limit
    )
