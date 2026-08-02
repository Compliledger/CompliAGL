"""Re-evaluation job — orchestrate an automated re-evaluation run.

Given a triggering :class:`MonitoringEvent`, the job:

1. runs :mod:`impact_analysis` to find every affected governed record,
2. never overwrites history — it creates a **new** immutable assessment and a
   **new** decision that supersedes the prior current decision (via
   :mod:`supersession_service`),
3. links every new record to the triggering event through the persisted
   :class:`ReevaluationRun`,
4. invalidates any outstanding authorization when the current conditions no
   longer support it (via :mod:`authorization_invalidation`),
5. generates a **new** AIProof that supersedes the prior proof — the prior proof
   is retained, not deleted (via :mod:`proof_supersession`),
6. publishes ``reevaluation.completed`` (and ``proof.superseded``) to ProofSync /
   AuditSync / RegSync as authorized.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.decision import Decision
from app.models.reevaluation_run import ReevaluationRun
from app.repositories.canonical import (
    AssessmentRepository,
    DecisionRepository,
    ReevaluationRunRepository,
)
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.canonical.errors import NotFoundError
from app.services.canonical.monitoring import (
    authorization_invalidation,
    impact_analysis,
    monitoring_service,
    proof_supersession,
    supersession_service,
)
from app.services.canonical.monitoring.change_detector import (
    INVALIDATING_CHANGE_TYPES,
    default_outcome,
)
from app.utils.canonical_enums import (
    AssessmentOutcome,
    DecisionOutcome,
    DecisionSupersessionStatus,
    IntegrationEventType,
    MonitoringChangeType,
    ReevaluationStatus,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now

# Assessment outcome that maps a re-evaluation decision outcome.
_OUTCOME_TO_ASSESSMENT = {
    DecisionOutcome.APPROVED.value: AssessmentOutcome.SATISFIED.value,
    DecisionOutcome.DENIED.value: AssessmentOutcome.NOT_SATISFIED.value,
    DecisionOutcome.ESCALATED.value: AssessmentOutcome.MANUAL_REVIEW_REQUIRED.value,
}


def _resolve_outcome(
    change_type: MonitoringChangeType,
    prior_decision: Optional[Decision],
    requested: Optional[str],
) -> str:
    """Determine the re-evaluated decision outcome deterministically."""
    if requested:
        return DecisionOutcome(requested).value
    default = default_outcome(change_type)
    if default is not None:
        return default.value
    if prior_decision is not None:
        return prior_decision.outcome
    return DecisionOutcome.APPROVED.value


def _should_invalidate_authorizations(
    change_type: MonitoringChangeType, outcome: str
) -> bool:
    if outcome != DecisionOutcome.APPROVED.value:
        return True
    return change_type in INVALIDATING_CHANGE_TYPES


def _create_assessment(
    db: Session,
    organization_id: str,
    *,
    evaluation_id: Optional[str],
    prior_decision: Optional[Decision],
    outcome: str,
    monitoring_event_id: str,
    reason_codes: list[str],
) -> Assessment:
    resolution_id = evaluation_id or "reevaluation"
    assessment_outcome = _OUTCOME_TO_ASSESSMENT.get(
        outcome, AssessmentOutcome.NOT_EVALUABLE.value
    )
    assessment_input = {
        "engine_version": DETERMINISTIC_ENGINE_VERSION,
        "organization_id": organization_id,
        "evaluation_id": resolution_id,
        "monitoring_event_id": monitoring_event_id,
        "prior_decision_id": prior_decision.id if prior_decision else None,
        "outcome": outcome,
    }
    input_hash = hash_dict(assessment_input)
    assessment = Assessment(
        organization_id=organization_id,
        evaluation_id=resolution_id,
        policy_resolution_id=resolution_id,
        evidence_sufficiency_id=None,
        control_evaluation_ids="[]",
        mandatory_control_summary=json.dumps(
            {"reevaluation_of_event": monitoring_event_id}
        ),
        evidence_sufficiency_result=None,
        overall_result=assessment_outcome,
        reason_codes=json.dumps(reason_codes),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=input_hash,
        assessment_hash=hash_dict(
            {
                "input_hash": input_hash,
                "overall_result": assessment_outcome,
                "reason_codes": reason_codes,
            }
        ),
        assessed_at=utc_now(),
    )
    return AssessmentRepository(db).add(assessment)


def _create_decision(
    db: Session,
    organization_id: str,
    *,
    intent_id: str,
    evaluation_id: Optional[str],
    prior_decision: Optional[Decision],
    assessment: Assessment,
    outcome: str,
    reason_codes: list[str],
) -> Decision:
    resolution_id = evaluation_id or "reevaluation"
    governance_evaluation_id = (
        (prior_decision.governance_evaluation_id if prior_decision else None)
        or evaluation_id
        or "reevaluation"
    )
    decision_input = {
        "engine_version": DETERMINISTIC_ENGINE_VERSION,
        "organization_id": organization_id,
        "evaluation_id": resolution_id,
        "assessment_id": assessment.id,
        "assessment_hash": assessment.assessment_hash,
        "outcome": outcome,
        "prior_decision_id": prior_decision.id if prior_decision else None,
    }
    input_hash = hash_dict(decision_input)
    decision = Decision(
        organization_id=organization_id,
        governance_evaluation_id=governance_evaluation_id,
        intent_id=intent_id,
        evaluation_id=resolution_id,
        policy_resolution_id=(
            prior_decision.policy_resolution_id if prior_decision else None
        ),
        assessment_id=assessment.id,
        outcome=outcome,
        reason_codes=json.dumps(reason_codes),
        policy_version=(prior_decision.policy_version if prior_decision else None),
        assessment_hash=assessment.assessment_hash,
        policy_package_hash=(
            prior_decision.policy_package_hash if prior_decision else None
        ),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=input_hash,
        decision_hash=hash_dict(
            {
                "input_hash": input_hash,
                "outcome": outcome,
                "reason_codes": reason_codes,
                "prior_decision_id": (
                    prior_decision.id if prior_decision else None
                ),
            }
        ),
        decided_at=utc_now(),
        prior_decision_id=prior_decision.id if prior_decision else None,
        supersession_status=DecisionSupersessionStatus.CURRENT.value,
    )
    return DecisionRepository(db).add(decision)


def trigger(
    db: Session,
    organization_id: str,
    monitoring_event_id: str,
    *,
    resulting_outcome: Optional[str] = None,
    reason: Optional[str] = None,
) -> ReevaluationRun:
    """Run an automated re-evaluation for a monitoring event."""
    event = monitoring_service.get(db, organization_id, monitoring_event_id)
    if event is None:
        raise NotFoundError(
            f"MonitoringEvent not found: {monitoring_event_id}"
        )

    change_type = MonitoringChangeType(event.change_type)
    run_repo = ReevaluationRunRepository(db)
    run = ReevaluationRun(
        organization_id=organization_id,
        monitoring_event_id=event.id,
        change_type=event.change_type,
        correlation_id=event.correlation_id,
        status=ReevaluationStatus.IN_PROGRESS.value,
    )
    run = run_repo.add(run)

    try:
        impact = impact_analysis.analyze(db, organization_id, event)
        run.impact = json.dumps(impact.to_dict())
        run.intent_id = impact.intent_id
        run.evaluation_id = impact.evaluation_id

        if impact.intent_id is None or impact.is_empty():
            run.status = ReevaluationStatus.NO_ACTION.value
            run.reason_codes = json.dumps(["REEVALUATION_NO_AFFECTED_RECORDS"])
            run.completed_at = utc_now()
            return run_repo.save(run)

        prior_decision = DecisionRepository(db).current_for_intent(
            organization_id, impact.intent_id
        )
        outcome = _resolve_outcome(change_type, prior_decision, resulting_outcome)

        reason_codes = [
            f"REEVALUATION_TRIGGERED_BY_{event.change_type}",
            f"MONITORING_EVENT_{event.id}",
            f"DECISION_{outcome}",
        ]
        if reason:
            reason_codes.append(f"REASON_{reason}")

        assessment = _create_assessment(
            db,
            organization_id,
            evaluation_id=impact.evaluation_id,
            prior_decision=prior_decision,
            outcome=outcome,
            monitoring_event_id=event.id,
            reason_codes=reason_codes,
        )
        new_decision = _create_decision(
            db,
            organization_id,
            intent_id=impact.intent_id,
            evaluation_id=impact.evaluation_id,
            prior_decision=prior_decision,
            assessment=assessment,
            outcome=outcome,
            reason_codes=reason_codes,
        )
        supersession_service.supersede_decision(db, prior_decision, new_decision)

        invalidated: list[str] = []
        if _should_invalidate_authorizations(change_type, outcome):
            invalidated = authorization_invalidation.invalidate_authorizations(
                db,
                organization_id,
                impact.authorizations,
                change_type=event.change_type,
                reason=(
                    reason
                    or f"reevaluation:{event.change_type}:{new_decision.id}"
                ),
            )

        new_proof, prior_proof = proof_supersession.supersede_proof(
            db,
            organization_id,
            new_decision,
            correlation_id=event.correlation_id,
        )

        run.prior_decision_id = prior_decision.id if prior_decision else None
        run.new_decision_id = new_decision.id
        run.new_assessment_id = assessment.id
        run.prior_aiproof_id = prior_proof.id if prior_proof else None
        run.new_aiproof_id = new_proof.id
        run.invalidated_authorization_ids = json.dumps(invalidated)
        run.resulting_outcome = outcome
        run.reason_codes = json.dumps(reason_codes)
        run.status = ReevaluationStatus.COMPLETED.value
        run.completed_at = utc_now()
        run = run_repo.save(run)

        _publish_reevaluation_completed(db, run, event, new_decision, new_proof)
        return run
    except Exception as exc:  # noqa: BLE001 - record failure, never lose the run
        db.rollback()
        run = run_repo.get(organization_id, run.id)
        if run is not None:
            run.status = ReevaluationStatus.FAILED.value
            run.error = str(exc)
            run.completed_at = utc_now()
            run_repo.save(run)
        raise


def _publish_reevaluation_completed(
    db: Session,
    run: ReevaluationRun,
    event,
    new_decision: Decision,
    new_proof,
) -> None:
    from app.services.canonical.integration import event_publisher
    from app.services.canonical.integration.contracts import EventContract

    event_publisher.emit_safe(
        db,
        EventContract(
            event_type=IntegrationEventType.REEVALUATION_COMPLETED,
            organization_id=run.organization_id,
            aggregate_type="ReevaluationRun",
            aggregate_id=run.id,
            references={
                "reevaluation_run_id": run.id,
                "monitoring_event_id": event.id,
                "intent_id": run.intent_id,
                "prior_decision_id": run.prior_decision_id,
                "decision_id": new_decision.id,
                "decision_hash": new_decision.decision_hash,
                "new_aiproof_id": new_proof.id if new_proof else None,
                "prior_aiproof_id": run.prior_aiproof_id,
                "proof_hash": new_proof.aiproof_hash if new_proof else None,
                "correlation_id": run.correlation_id,
            },
            attributes={
                "status": run.status,
                "change_type": run.change_type,
                "outcome": run.resulting_outcome,
            },
            dedup_key=f"reevaluation:{run.id}",
        ),
    )


def get(
    db: Session, organization_id: str, run_id: str
) -> Optional[ReevaluationRun]:
    return ReevaluationRunRepository(db).get(organization_id, run_id)


def list_(
    db: Session,
    organization_id: str,
    *,
    status: Optional[str] = None,
    intent_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    return ReevaluationRunRepository(db).list_filtered(
        organization_id,
        status=status,
        intent_id=intent_id,
        skip=skip,
        limit=limit,
    )
