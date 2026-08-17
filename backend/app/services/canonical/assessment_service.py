"""Assessment service — deterministic runtime stage.

Assessment runs **after** Control Evaluation and **before** the Decision stage.
It aggregates the control evaluations for one evaluation into a single, factual
verdict **without** producing the final business decision.

Assessment is deliberately factual. Its outcome is one of ``SATISFIED``,
``NOT_SATISFIED``, ``NOT_EVALUABLE`` or ``MANUAL_REVIEW_REQUIRED`` — it never
emits ``APPROVED`` / ``DENIED`` / ``ESCALATED``. Mapping an assessment (together
with explicit decision conditions) into a business decision is the separate
Decision stage.

Only **mandatory** controls drive the aggregate outcome; optional-control
failures are recorded in the summary but never change the assessment result.
The aggregation precedence is fail-closed: ``MANUAL_REVIEW_REQUIRED`` >
``NOT_EVALUABLE`` > ``NOT_SATISFIED`` > ``SATISFIED``.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.repositories.canonical import AssessmentRepository
from app.services.canonical import (
    control_evaluation_service,
    evidence_sufficiency_service,
)
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.utils.canonical_enums import (
    AssessmentOutcome,
    ControlEvaluationOutcome,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def _aggregate(mandatory_results: list[str]) -> tuple[str, list[str]]:
    """Aggregate mandatory control results into the assessment outcome."""
    if not mandatory_results:
        return (
            AssessmentOutcome.SATISFIED.value,
            ["ASSESSMENT_SATISFIED_NO_MANDATORY_CONTROLS"],
        )
    C = ControlEvaluationOutcome
    if C.MANUAL_REVIEW_REQUIRED.value in mandatory_results:
        return (
            AssessmentOutcome.MANUAL_REVIEW_REQUIRED.value,
            ["ASSESSMENT_MANUAL_REVIEW_REQUIRED"],
        )
    if C.NOT_EVALUABLE.value in mandatory_results:
        return (
            AssessmentOutcome.NOT_EVALUABLE.value,
            ["ASSESSMENT_NOT_EVALUABLE_MANDATORY_CONTROL"],
        )
    if C.NOT_SATISFIED.value in mandatory_results:
        return (
            AssessmentOutcome.NOT_SATISFIED.value,
            ["ASSESSMENT_NOT_SATISFIED_MANDATORY_CONTROL"],
        )
    return (
        AssessmentOutcome.SATISFIED.value,
        ["ASSESSMENT_SATISFIED_ALL_MANDATORY_CONTROLS"],
    )


def assess_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> Assessment:
    """Aggregate control evaluations for a resolution and persist the record."""
    org = organization_id

    sufficiency = evidence_sufficiency_service.evaluate_or_get_for_resolution(
        db, org, policy_resolution_id
    )
    control_evaluations = control_evaluation_service.evaluate_for_resolution(
        db, org, policy_resolution_id
    )

    # Deterministic ordering by control evaluation id.
    ordered = sorted(
        control_evaluations, key=lambda ce: ce.control_evaluation_id
    )

    mandatory_results = [ce.result for ce in ordered if ce.mandatory]
    optional_results = [ce.result for ce in ordered if not ce.mandatory]

    def _count(results: list[str], outcome: str) -> int:
        return sum(1 for r in results if r == outcome)

    C = ControlEvaluationOutcome
    mandatory_control_summary = {
        "total": len(mandatory_results),
        "satisfied": _count(mandatory_results, C.SATISFIED.value),
        "not_satisfied": _count(mandatory_results, C.NOT_SATISFIED.value),
        "not_evaluable": _count(mandatory_results, C.NOT_EVALUABLE.value),
        "manual_review_required": _count(
            mandatory_results, C.MANUAL_REVIEW_REQUIRED.value
        ),
        "optional_total": len(optional_results),
        "optional_satisfied": _count(optional_results, C.SATISFIED.value),
    }

    overall_result, aggregate_reasons = _aggregate(mandatory_results)
    reason_codes = ["ASSESSMENT_AGGREGATED"] + aggregate_reasons

    control_summaries = [
        {
            "control_evaluation_id": ce.control_evaluation_id,
            "control_id": ce.control_id,
            "mandatory": ce.mandatory,
            "result": ce.result,
            "result_hash": ce.result_hash,
        }
        for ce in ordered
    ]
    control_evaluation_ids = [ce.control_evaluation_id for ce in ordered]

    input_hash = hash_dict(
        {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "organization_id": org,
            "policy_resolution_id": policy_resolution_id,
            # evidence_sufficiency_result_hash (a deterministic content hash)
            # is the input identity here, not sufficiency.id -- sufficiency
            # rows aren't deduped by evaluate_for_resolution (each direct
            # call creates a fresh, immutable row like Decision/Assessment
            # themselves), so a random per-row id must never leak into a
            # "deterministic inputs" hash. See decision_service.py's
            # identical fix for assessment_id/assessment_hash.
            "evidence_sufficiency_result": sufficiency.overall_result,
            "evidence_sufficiency_result_hash": sufficiency.result_hash,
            "control_evaluations": control_summaries,
        }
    )
    assessment_hash = hash_dict(
        {
            "input_hash": input_hash,
            "overall_result": overall_result,
            "mandatory_control_summary": mandatory_control_summary,
            "reason_codes": reason_codes,
        }
    )

    obj = Assessment(
        organization_id=org,
        evaluation_id=policy_resolution_id,
        policy_resolution_id=policy_resolution_id,
        applicable_control_set_id=(
            ordered[0].applicable_control_set_id if ordered else None
        ),
        evidence_sufficiency_id=sufficiency.id,
        control_evaluation_ids=json.dumps(control_evaluation_ids),
        mandatory_control_summary=json.dumps(mandatory_control_summary),
        evidence_sufficiency_result=sufficiency.overall_result,
        overall_result=overall_result,
        reason_codes=json.dumps(reason_codes),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=input_hash,
        assessment_hash=assessment_hash,
        assessed_at=utc_now(),
    )
    return AssessmentRepository(db).add(obj)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[Assessment]:
    return AssessmentRepository(db).get(organization_id, resource_id)


def latest_for_resolution(
    db: Session, organization_id: str, policy_resolution_id: str
) -> Optional[Assessment]:
    return AssessmentRepository(db).latest_for_resolution(
        organization_id, policy_resolution_id
    )


def list_(
    db: Session,
    organization_id: str,
    *,
    policy_resolution_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[Assessment]:
    repo = AssessmentRepository(db)
    if policy_resolution_id is not None:
        return repo.list_for_resolution(
            organization_id, policy_resolution_id, skip=skip, limit=limit
        )
    return repo.list(organization_id, skip=skip, limit=limit)
