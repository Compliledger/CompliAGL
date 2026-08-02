"""Applicability Evaluation service — deterministic runtime stage #2.

Applicability Evaluation runs **after** Policy Resolution and **independently of**
the decision engine. For a completed :class:`PolicyResolution` it evaluates each
candidate requirement of every selected package independently, using only the
restricted deterministic expression engine, and produces exactly one of:

* ``APPLICABLE``,
* ``NOT_APPLICABLE``,
* ``CONDITIONAL``,
* ``INDETERMINATE``.

``INDETERMINATE`` (produced when required context is missing) is a first-class
result and is **never** silently treated as ``NOT_APPLICABLE`` — this is what
prevents missing context from silently producing approval downstream.

Each result is persisted as an :class:`ApplicabilityEvaluation` record capturing
the factual basis, input references, reason codes, engine version and
deterministic hashes required for audit and replay.

A requirement declares its deterministic applicability via two optional keys on
the requirement definition:

* ``applicability_criteria`` — a structured expression that decides
  APPLICABLE vs NOT_APPLICABLE (INDETERMINATE when facts are missing).
* ``condition_criteria`` — an optional structured expression evaluated only
  when the requirement is applicable; an unmet condition yields ``CONDITIONAL``.

If no ``applicability_criteria`` is present the requirement is unconditionally
applicable (the governing package was already scoped during resolution).
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.applicability_evaluation import ApplicabilityEvaluation
from app.models.policy_resolution import PolicyResolution
from app.repositories.canonical import (
    ActorIdentityRepository,
    ApplicabilityEvaluationRepository,
    ExecutableGovernancePackageRepository,
    IntentRepository,
    OperationalContextRepository,
    PolicyResolutionRepository,
    TargetRepository,
)
from app.schemas.canonical.policy_applicability import (
    ApplicabilityEvaluationCreate,
)
from app.services.canonical import runtime_facts
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
    EvaluationOutcome,
    ExpressionError,
    TriState,
    default_engine,
)
from app.services.canonical.errors import NotFoundError
from app.utils.canonical_enums import ApplicabilityResult
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def _load(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _derive_result(
    applicability: Optional[dict[str, Any]],
    condition: Optional[dict[str, Any]],
    facts: dict[str, Any],
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Deterministically derive the applicability result.

    Returns ``(result, reason_codes, observed_values)``.
    """
    observed: list[dict[str, Any]] = []

    # No criteria → unconditionally applicable (package already scoped).
    if applicability is None:
        return (
            ApplicabilityResult.APPLICABLE.value,
            ["APPLICABLE_NO_CRITERIA"],
            observed,
        )

    try:
        app_outcome = default_engine.evaluate(applicability, facts)
    except ExpressionError as exc:
        # A malformed expression is a definition defect; surface as
        # INDETERMINATE rather than guessing an applicability answer.
        return (
            ApplicabilityResult.INDETERMINATE.value,
            ["INDETERMINATE_INVALID_EXPRESSION", str(exc)],
            observed,
        )
    observed.extend(app_outcome.observed)

    if app_outcome.value is TriState.FALSE:
        return (
            ApplicabilityResult.NOT_APPLICABLE.value,
            ["NOT_APPLICABLE_BY_CRITERIA"],
            observed,
        )
    if app_outcome.value is TriState.INDETERMINATE:
        return (
            ApplicabilityResult.INDETERMINATE.value,
            _missing_reason(app_outcome, "INDETERMINATE_MISSING_INPUT"),
            observed,
        )

    # Applicability is TRUE — evaluate the optional condition.
    if condition is None:
        return (
            ApplicabilityResult.APPLICABLE.value,
            ["APPLICABLE_BY_CRITERIA"],
            observed,
        )

    try:
        cond_outcome = default_engine.evaluate(condition, facts)
    except ExpressionError as exc:
        return (
            ApplicabilityResult.INDETERMINATE.value,
            ["INDETERMINATE_INVALID_CONDITION", str(exc)],
            observed,
        )
    observed.extend(cond_outcome.observed)

    if cond_outcome.value is TriState.TRUE:
        return (
            ApplicabilityResult.APPLICABLE.value,
            ["APPLICABLE_CONDITION_SATISFIED"],
            observed,
        )
    if cond_outcome.value is TriState.FALSE:
        return (
            ApplicabilityResult.CONDITIONAL.value,
            ["CONDITIONAL_UNMET_CONDITION"],
            observed,
        )
    return (
        ApplicabilityResult.INDETERMINATE.value,
        _missing_reason(cond_outcome, "INDETERMINATE_CONDITION_MISSING_INPUT"),
        observed,
    )


def _missing_reason(outcome: EvaluationOutcome, code: str) -> list[str]:
    reasons = [code]
    for field_path in outcome.missing_fields:
        reasons.append(f"MISSING:{field_path}")
    return reasons


def _dedupe_observed(observed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for entry in observed:
        key = entry.get("field")
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def evaluate_for_resolution(
    db: Session, payload: ApplicabilityEvaluationCreate
) -> list[ApplicabilityEvaluation]:
    """Evaluate every candidate requirement for a resolution and persist results."""
    org = payload.organization_id
    resolution = PolicyResolutionRepository(db).get(
        org, payload.policy_resolution_id
    )
    if resolution is None:
        raise NotFoundError(
            f"PolicyResolution not found: {payload.policy_resolution_id}"
        )

    actor = ActorIdentityRepository(db).get(org, resolution.actor_identity_id)
    intent = IntentRepository(db).get(org, resolution.intent_id)
    if actor is None or intent is None:
        raise NotFoundError(
            "Resolution references an actor or intent that no longer exists"
        )

    target = None
    if resolution.target_id:
        target = TargetRepository(db).get(org, resolution.target_id)
    context = None
    if resolution.operational_context_id:
        context = OperationalContextRepository(db).get(
            org, resolution.operational_context_id
        )

    facts = runtime_facts.build_facts(
        actor=actor, intent=intent, target=target, context=context
    )

    selected_packages = _load(resolution.selected_packages) or []
    pkg_repo = ExecutableGovernancePackageRepository(db)
    result_repo = ApplicabilityEvaluationRepository(db)

    records: list[ApplicabilityEvaluation] = []
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
        requirement_defs = {
            r.get("requirement_id"): r
            for r in (_load(package.requirements) or [])
            if isinstance(r, dict) and r.get("requirement_id")
        }

        for selected_req in selected.get("requirements", []):
            if not isinstance(selected_req, dict):
                continue
            requirement_id = selected_req.get("requirement_id")
            if not requirement_id:
                continue
            requirement_version = selected_req.get("requirement_version")
            definition = requirement_defs.get(requirement_id, {})
            applicability = definition.get("applicability_criteria")
            condition = definition.get("condition_criteria")

            result, reason_codes, observed = _derive_result(
                applicability, condition, facts
            )
            observed = _dedupe_observed(observed)
            evaluated_expression = {
                "applicability": applicability,
                "condition": condition,
            }

            input_hash = hash_dict(
                {
                    "engine_version": DETERMINISTIC_ENGINE_VERSION,
                    "organization_id": org,
                    "actor_identity_id": resolution.actor_identity_id,
                    "intent_id": resolution.intent_id,
                    "target_id": resolution.target_id,
                    "operational_context_id": resolution.operational_context_id,
                    "package_id": package_id,
                    "package_version": package_version,
                    "requirement_id": requirement_id,
                    "requirement_version": requirement_version,
                    "expression": evaluated_expression,
                    "observed_values": observed,
                }
            )
            result_hash = hash_dict(
                {
                    "input_hash": input_hash,
                    "result": result,
                    "reason_codes": reason_codes,
                    "observed_values": observed,
                }
            )

            obj = ApplicabilityEvaluation(
                organization_id=org,
                policy_resolution_id=resolution.id,
                actor_identity_id=resolution.actor_identity_id,
                intent_id=resolution.intent_id,
                target_id=resolution.target_id,
                operational_context_id=resolution.operational_context_id,
                package_id=package_id,
                package_version=package_version,
                requirement_id=requirement_id,
                requirement_version=requirement_version,
                result=result,
                evaluated_expression=json.dumps(evaluated_expression),
                observed_values=json.dumps(observed),
                reason_codes=json.dumps(reason_codes),
                engine_version=DETERMINISTIC_ENGINE_VERSION,
                input_hash=input_hash,
                result_hash=result_hash,
                evaluated_at=utc_now(),
            )
            records.append(result_repo.add(obj))

    return records


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[ApplicabilityEvaluation]:
    return ApplicabilityEvaluationRepository(db).get(organization_id, resource_id)


def list_(
    db: Session,
    organization_id: str,
    *,
    policy_resolution_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[ApplicabilityEvaluation]:
    repo = ApplicabilityEvaluationRepository(db)
    if policy_resolution_id is not None:
        return repo.list_for_resolution(
            organization_id, policy_resolution_id, skip=skip, limit=limit
        )
    return repo.list(organization_id, skip=skip, limit=limit)
