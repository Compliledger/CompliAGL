"""Re-assessment service — closes the resolution lifecycle.

After a finding's resolution has been *validated*, re-assessment produces new,
immutable assessment and decision records that reference the prior decision and
the finding. It enforces the branch's governance rules:

1. Prior decisions remain immutable (a new decision is created; the prior is only
   marked ``SUPERSEDED``).
2. Re-assessment creates new assessment and decision records.
3. New records reference the prior decision and the finding.
4. Only a new ``APPROVED`` decision may later produce authorization.
5. Terminal denials terminate the current intent.
6. Manual review must have produced a review record and reviewer identity.
7. Marking remediation complete is not proof of resolution — re-assessment only
   proceeds from a *validated* resolution.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.decision import Decision
from app.repositories.canonical import (
    AssessmentRepository,
    DecisionRepository,
    FindingRepository,
    IntentRepository,
    ReviewRecordRepository,
)
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.canonical.errors import NotFoundError
from app.utils.canonical_enums import (
    AssessmentOutcome,
    DecisionOutcome,
    DecisionSupersessionStatus,
    FindingStatus,
    FindingType,
    IntentStatus,
    ResolutionValidationOutcome,
    ReviewOutcome,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def _terminate_intent(db: Session, org: str, intent_id: str | None) -> None:
    if not intent_id:
        return
    repo = IntentRepository(db)
    intent = repo.get(org, intent_id)
    if intent is not None and intent.status not in {
        IntentStatus.EXECUTED.value,
        IntentStatus.CANCELLED.value,
    }:
        intent.status = IntentStatus.DENIED.value
        repo.save(intent)


def trigger(
    db: Session, organization_id: str, finding_id: str
) -> dict[str, Any]:
    """Trigger re-assessment for a finding with a validated resolution."""
    org = organization_id
    finding = FindingRepository(db).get(org, finding_id)
    if finding is None:
        raise NotFoundError(f"Finding not found: {finding_id}")

    # --- Rule 5: terminal denials terminate the current intent ------------- #
    if finding.terminal:
        finding.status = FindingStatus.TERMINATED.value
        FindingRepository(db).save(finding)
        _terminate_intent(db, org, finding.intent_id)
        return {
            "finding_id": finding.finding_id,
            "reassessed": False,
            "reason_codes": ["REASSESS_BLOCKED_TERMINAL", "INTENT_TERMINATED"],
            "prior_decision_id": finding.decision_id,
            "new_decision_id": None,
            "new_assessment_id": None,
            "decision_outcome": None,
            "finding_status": finding.status,
        }

    # --- Rule 7: only a validated resolution may proceed ------------------- #
    if (
        finding.resolution_validation_outcome
        != ResolutionValidationOutcome.VALIDATED.value
    ):
        return {
            "finding_id": finding.finding_id,
            "reassessed": False,
            "reason_codes": ["REASSESS_BLOCKED_RESOLUTION_NOT_VALIDATED"],
            "prior_decision_id": finding.decision_id,
            "new_decision_id": None,
            "new_assessment_id": None,
            "decision_outcome": None,
            "finding_status": finding.status,
        }

    # --- Rule 6: manual review must have a reviewer identity --------------- #
    if finding.finding_type == FindingType.MANUAL_REVIEW.value:
        reviews = ReviewRecordRepository(db).list_for_finding(org, finding.id)
        if not any(r.outcome == ReviewOutcome.APPROVED.value for r in reviews):
            return {
                "finding_id": finding.finding_id,
                "reassessed": False,
                "reason_codes": ["REASSESS_BLOCKED_NO_APPROVING_REVIEW"],
                "prior_decision_id": finding.decision_id,
                "new_decision_id": None,
                "new_assessment_id": None,
                "decision_outcome": None,
                "finding_status": finding.status,
            }

    prior_decision = (
        DecisionRepository(db).get(org, finding.decision_id)
        if finding.decision_id
        else None
    )
    resolution_id = finding.evaluation_id

    # --- Rule 2 + 3: new assessment referencing the prior + finding -------- #
    now = utc_now()
    assessment_reason_codes = [
        "REASSESSMENT_AGGREGATED",
        "REASSESSMENT_RESOLUTION_VALIDATED",
        f"PRIOR_ASSESSMENT_{finding.assessment_id}",
        f"ORIGIN_FINDING_{finding.finding_id}",
    ]
    assessment_input = {
        "engine_version": DETERMINISTIC_ENGINE_VERSION,
        "organization_id": org,
        "policy_resolution_id": resolution_id,
        "finding_id": finding.id,
        "prior_assessment_id": finding.assessment_id,
        "resolution_validation_outcome": finding.resolution_validation_outcome,
    }
    assessment_input_hash = hash_dict(assessment_input)
    new_assessment = Assessment(
        organization_id=org,
        evaluation_id=resolution_id,
        policy_resolution_id=resolution_id or "reassessment",
        evidence_sufficiency_id=None,
        control_evaluation_ids="[]",
        mandatory_control_summary=json.dumps(
            {"reassessment_of_finding": finding.finding_id}
        ),
        evidence_sufficiency_result=None,
        overall_result=AssessmentOutcome.SATISFIED.value,
        reason_codes=json.dumps(assessment_reason_codes),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=assessment_input_hash,
        assessment_hash=hash_dict(
            {
                "input_hash": assessment_input_hash,
                "overall_result": AssessmentOutcome.SATISFIED.value,
                "reason_codes": assessment_reason_codes,
            }
        ),
        assessed_at=now,
    )
    new_assessment = AssessmentRepository(db).add(new_assessment)

    # --- New deterministic decision (APPROVED) ----------------------------- #
    decision_reason_codes = [
        f"DECISION_{DecisionOutcome.APPROVED.value}",
        "APPROVED_AFTER_REASSESSMENT",
        f"RESOLVED_FINDING_{finding.finding_id}",
    ]
    decision_input = {
        "engine_version": DETERMINISTIC_ENGINE_VERSION,
        "organization_id": org,
        "policy_resolution_id": resolution_id,
        "assessment_id": new_assessment.id,
        "assessment_hash": new_assessment.assessment_hash,
        "assessment_result": new_assessment.overall_result,
        "prior_decision_id": finding.decision_id,
        "originating_finding_id": finding.id,
    }
    decision_input_hash = hash_dict(decision_input)
    decided_at = utc_now()
    new_decision = Decision(
        organization_id=org,
        governance_evaluation_id=resolution_id or "reassessment",
        intent_id=finding.intent_id or "",
        evaluation_id=resolution_id,
        policy_resolution_id=resolution_id,
        assessment_id=new_assessment.id,
        outcome=DecisionOutcome.APPROVED.value,
        reason_codes=json.dumps(decision_reason_codes),
        policy_version=(prior_decision.policy_version if prior_decision else None),
        assessment_hash=new_assessment.assessment_hash,
        policy_package_hash=(
            prior_decision.policy_package_hash if prior_decision else None
        ),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=decision_input_hash,
        decision_hash=hash_dict(
            {
                "input_hash": decision_input_hash,
                "outcome": DecisionOutcome.APPROVED.value,
                "reason_codes": decision_reason_codes,
                "prior_decision_id": finding.decision_id,
            }
        ),
        decided_at=decided_at,
        prior_decision_id=finding.decision_id,
        originating_finding_id=finding.id,
        supersession_status=DecisionSupersessionStatus.CURRENT.value,
    )
    repo = DecisionRepository(db)
    new_decision = repo.add(new_decision)

    # --- Rule 1: prior decision immutable, only marked SUPERSEDED ----------- #
    if prior_decision is not None and prior_decision.id != new_decision.id:
        prior_decision.supersession_status = (
            DecisionSupersessionStatus.SUPERSEDED.value
        )
        prior_decision.superseded_by_decision_id = new_decision.id
        repo.save(prior_decision)

    # --- Close the finding ------------------------------------------------- #
    finding.status = FindingStatus.CLOSED.value
    finding.resolved_by_decision_id = new_decision.id
    FindingRepository(db).save(finding)

    # --- Integration events (best-effort; never breaks governance) --------- #
    _emit_reevaluation_events(
        db, org, finding, prior_decision, new_decision, new_assessment
    )

    return {
        "finding_id": finding.finding_id,
        "reassessed": True,
        "reason_codes": ["REASSESSMENT_COMPLETE", *decision_reason_codes],
        "prior_decision_id": finding.decision_id,
        "new_decision_id": new_decision.id,
        "new_assessment_id": new_assessment.id,
        "decision_outcome": new_decision.outcome,
        "finding_status": finding.status,
    }


def _emit_reevaluation_events(
    db: Session,
    org: str,
    finding,
    prior_decision,
    new_decision,
    new_assessment,
) -> None:
    """Publish reevaluation.completed + proof.superseded events (best-effort).

    A validated resolution produces a new decision and supersedes the prior one.
    That supersession is propagated to the sync portals so a stale proof view is
    never treated as current: ``proof.superseded`` marks the prior decision/proof
    and ``reevaluation.completed`` announces the new current decision.
    """
    from app.services.canonical.integration import event_publisher
    from app.services.canonical.integration.contracts import EventContract
    from app.utils.canonical_enums import IntegrationEventType

    if prior_decision is not None and prior_decision.id != new_decision.id:
        event_publisher.emit_safe(
            db,
            EventContract(
                event_type=IntegrationEventType.PROOF_SUPERSEDED,
                organization_id=org,
                aggregate_type="Decision",
                aggregate_id=prior_decision.id,
                references={
                    "decision_id": prior_decision.id,
                    "decision_hash": prior_decision.decision_hash,
                    "superseded_by_decision_id": new_decision.id,
                    "intent_id": finding.intent_id,
                    "finding_id": finding.finding_id,
                },
                attributes={
                    "status": DecisionSupersessionStatus.SUPERSEDED.value,
                    "outcome": prior_decision.outcome,
                },
                dedup_key=f"superseded_by:{new_decision.id}",
            ),
        )

    event_publisher.emit_safe(
        db,
        EventContract(
            event_type=IntegrationEventType.REEVALUATION_COMPLETED,
            organization_id=org,
            aggregate_type="Decision",
            aggregate_id=new_decision.id,
            references={
                "decision_id": new_decision.id,
                "decision_hash": new_decision.decision_hash,
                "prior_decision_id": (
                    prior_decision.id if prior_decision is not None else None
                ),
                "assessment_id": new_assessment.id,
                "intent_id": finding.intent_id,
                "finding_id": finding.finding_id,
            },
            attributes={
                "status": new_decision.supersession_status,
                "outcome": new_decision.outcome,
                "finding_status": finding.status,
            },
        ),
    )


def decision_history(
    db: Session, organization_id: str, intent_id: str
) -> dict[str, Any]:
    """Return the full, ordered decision history and findings for an intent."""
    org = organization_id
    decisions = [
        d
        for d in DecisionRepository(db)._scoped(org)  # noqa: SLF001
        .filter(Decision.intent_id == intent_id)
        .order_by(Decision.created_at.asc())
        .all()
    ]
    entries = [
        {
            "decision_id": d.id,
            "outcome": d.outcome,
            "supersession_status": d.supersession_status,
            "prior_decision_id": d.prior_decision_id,
            "superseded_by_decision_id": d.superseded_by_decision_id,
            "originating_finding_id": getattr(d, "originating_finding_id", None),
            "decision_hash": d.decision_hash,
            "decided_at": d.decided_at,
            "reason_codes": json.loads(d.reason_codes or "[]"),
        }
        for d in decisions
    ]
    findings = FindingRepository(db).list_filtered(org, intent_id=intent_id)
    return {"intent_id": intent_id, "decisions": entries, "findings": findings}
