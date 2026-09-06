"""Tests for the CompliAGL finding and remediation branch.

Covers finding generation from the deterministic pipeline, the DevSync
integration, resolution evidence validation (reusing the evidence architecture),
manual-review resolution, terminal prohibition, decision immutability and the
new deterministic decision produced by re-assessment.
"""

from __future__ import annotations

import json
import uuid

from datetime import timedelta

import pytest

from app.models.assessment import Assessment
from app.models.control_evaluation import ControlEvaluation
from app.models.decision import Decision
from app.models.escalation_approval import EscalationApproval
from app.models.intent import Intent
from app.repositories.canonical import (
    AssessmentRepository,
    ControlEvaluationRepository,
    DecisionRepository,
    EscalationApprovalRepository,
    IntentRepository,
)
from app.schemas.canonical.remediation import (
    DevSyncCallbackEvidence,
    DevSyncCallbackRequest,
    DevSyncDispatchRequest,
    RemediationPlanCreate,
    RequiredResolutionEvidenceModel,
    ResolutionEvidenceSubmit,
    ReviewRecordCreate,
)
from app.services.canonical import (
    authorization_service,
    devsync_service,
    finding_service,
    reassessment_service,
    remediation_service,
    resolution_evidence_service,
    resolution_validation_service,
    review_service,
)
from app.services.canonical.errors import ConflictError
from app.utils.canonical_enums import (
    AssessmentOutcome,
    ControlEvaluationOutcome,
    DecisionOutcome,
    DecisionSupersessionStatus,
    DevSyncCallbackStatus,
    EscalationApprovalStatus,
    FindingStatus,
    FindingType,
    RemediationEligibility,
    ResolutionValidationOutcome,
    ReviewOutcome,
    ReviewType,
)
from app.utils.timestamps import utc_now

ORG = "org-remediation"


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def _mk_intent(db, org=ORG, amount=25000):
    intent = Intent(
        organization_id=org,
        intent_type="PAYMENT",
        action="book_flight",
        actor_id="actor-1",
        amount_minor=amount,
        amount_currency="USD",
    )
    return IntentRepository(db).add(intent)


def _mk_control_eval(
    db,
    resolution_id,
    *,
    result,
    control_id="CTRL-1",
    severity="HIGH",
    requirement_ids=("REQ-1",),
    reasons=("CONTROL_NOT_SATISFIED",),
    org=ORG,
):
    ce = ControlEvaluation(
        organization_id=org,
        evaluation_id=resolution_id,
        policy_resolution_id=resolution_id,
        control_evaluation_id=f"ce-{uuid.uuid4().hex[:8]}",
        control_id=control_id,
        mandatory=True,
        severity=severity,
        requirement_ids=json.dumps(list(requirement_ids)),
        evidence_requirement_ids=json.dumps(["EVREQ-1"]),
        result=result,
        reason_codes=json.dumps(list(reasons)),
        engine_version="test",
    )
    return ControlEvaluationRepository(db).add(ce)


def _mk_assessment(db, resolution_id, *, overall_result, org=ORG):
    a = Assessment(
        organization_id=org,
        evaluation_id=resolution_id,
        policy_resolution_id=resolution_id,
        control_evaluation_ids="[]",
        mandatory_control_summary="{}",
        overall_result=overall_result,
        reason_codes="[]",
        engine_version="test",
        assessment_hash="ah-" + resolution_id,
    )
    return AssessmentRepository(db).add(a)


def _mk_decision(
    db,
    intent_id,
    resolution_id,
    assessment_id,
    *,
    outcome,
    reason_codes,
    triggered=None,
    org=ORG,
):
    d = Decision(
        organization_id=org,
        governance_evaluation_id=resolution_id,
        intent_id=intent_id,
        evaluation_id=resolution_id,
        policy_resolution_id=resolution_id,
        assessment_id=assessment_id,
        outcome=outcome,
        reason_codes=json.dumps(reason_codes),
        decision_conditions_triggered=json.dumps(triggered or []),
        decision_hash="dh-" + uuid.uuid4().hex[:12],
        supersession_status=DecisionSupersessionStatus.CURRENT.value,
        decided_at=utc_now(),
    )
    return DecisionRepository(db).add(d)


def _escalated_control_failure(db, control_id="CTRL-1"):
    """Set up an ESCALATED decision with one failing (remediable) control."""
    intent = _mk_intent(db)
    resolution_id = "res-" + uuid.uuid4().hex[:8]
    _mk_control_eval(
        db,
        resolution_id,
        result=ControlEvaluationOutcome.NOT_SATISFIED.value,
        control_id=control_id,
    )
    assessment = _mk_assessment(
        db, resolution_id, overall_result=AssessmentOutcome.NOT_SATISFIED.value
    )
    decision = _mk_decision(
        db,
        intent.id,
        resolution_id,
        assessment.id,
        outcome=DecisionOutcome.ESCALATED.value,
        reason_codes=["DECISION_ESCALATED", "CONTROL_REMEDIATION_REQUIRED"],
    )
    return intent, resolution_id, assessment, decision


# --------------------------------------------------------------------------- #
# Finding generation
# --------------------------------------------------------------------------- #
def test_finding_generated_for_control_failure(db_session):
    _, _, _, decision = _escalated_control_failure(db_session)
    findings = finding_service.generate_for_decision(db_session, ORG, decision.id)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == FindingType.CONTROL_FAILURE.value
    assert finding.remediation_eligibility == RemediationEligibility.ELIGIBLE.value
    assert finding.terminal is False
    assert finding.status == FindingStatus.OPEN.value
    assert "CTRL-1" in json.loads(finding.control_ids)
    # Generation is idempotent.
    again = finding_service.generate_for_decision(db_session, ORG, decision.id)
    assert {f.id for f in again} == {finding.id}


def test_assign_finding_moves_to_assigned(db_session):
    _, _, _, decision = _escalated_control_failure(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]
    assigned = finding_service.assign(
        db_session, ORG, finding.id, owner="dev-team"
    )
    assert assigned.owner == "dev-team"
    assert assigned.status == FindingStatus.ASSIGNED.value


# --------------------------------------------------------------------------- #
# 1. Manager approval resolves escalation
# --------------------------------------------------------------------------- #
def test_manager_approval_resolves_escalation(db_session):
    intent = _mk_intent(db_session)
    resolution_id = "res-" + uuid.uuid4().hex[:8]
    _mk_control_eval(
        db_session,
        resolution_id,
        result=ControlEvaluationOutcome.MANUAL_REVIEW_REQUIRED.value,
        control_id="CTRL-MR",
        reasons=("CONTROL_MANUAL_REVIEW_REQUIRED",),
    )
    assessment = _mk_assessment(
        db_session,
        resolution_id,
        overall_result=AssessmentOutcome.MANUAL_REVIEW_REQUIRED.value,
    )
    decision = _mk_decision(
        db_session,
        intent.id,
        resolution_id,
        assessment.id,
        outcome=DecisionOutcome.ESCALATED.value,
        reason_codes=["DECISION_ESCALATED", "ASSESSMENT_MANUAL_REVIEW_REQUIRED"],
    )
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]
    assert finding.finding_type == FindingType.MANUAL_REVIEW.value

    # A manager review record with reviewer identity resolves the escalation.
    review_service.record(
        db_session,
        ReviewRecordCreate(
            organization_id=ORG,
            finding_id=finding.id,
            reviewer_id="manager-42",
            reviewer_role="MANAGER",
            review_type=ReviewType.ESCALATION_APPROVAL,
            outcome=ReviewOutcome.APPROVED,
            rationale="Reviewed and approved.",
        ),
    )

    result = resolution_validation_service.validate(db_session, ORG, finding.id)
    assert result["outcome"] == ResolutionValidationOutcome.VALIDATED.value

    reassessed = reassessment_service.trigger(db_session, ORG, finding.id)
    assert reassessed["reassessed"] is True
    assert reassessed["decision_outcome"] == DecisionOutcome.APPROVED.value

    refreshed = finding_service.get(db_session, ORG, finding.id)
    assert refreshed.status == FindingStatus.CLOSED.value


def test_manual_review_requires_reviewer_identity(db_session):
    """Manual review cannot be resolved without an approving review record."""
    intent = _mk_intent(db_session)
    resolution_id = "res-" + uuid.uuid4().hex[:8]
    _mk_control_eval(
        db_session,
        resolution_id,
        result=ControlEvaluationOutcome.MANUAL_REVIEW_REQUIRED.value,
        control_id="CTRL-MR",
    )
    assessment = _mk_assessment(
        db_session,
        resolution_id,
        overall_result=AssessmentOutcome.MANUAL_REVIEW_REQUIRED.value,
    )
    decision = _mk_decision(
        db_session,
        intent.id,
        resolution_id,
        assessment.id,
        outcome=DecisionOutcome.ESCALATED.value,
        reason_codes=["DECISION_ESCALATED"],
    )
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]

    # No review yet -> validation is insufficient and re-assessment is blocked.
    result = resolution_validation_service.validate(db_session, ORG, finding.id)
    assert result["outcome"] != ResolutionValidationOutcome.VALIDATED.value
    reassessed = reassessment_service.trigger(db_session, ORG, finding.id)
    assert reassessed["reassessed"] is False


# --------------------------------------------------------------------------- #
# 2. Developer remediation through a DevSync callback
# --------------------------------------------------------------------------- #
def _dispatch_and_plan(db_session, finding, evidence_type="code_fix_attestation",
                       allowed_issuers=("ci-system",)):
    plan = remediation_service.create_plan(
        db_session,
        RemediationPlanCreate(
            organization_id=ORG,
            finding_id=finding.id,
            required_corrective_state="control passes",
            required_resolution_evidence=[
                RequiredResolutionEvidenceModel(
                    evidence_type=evidence_type,
                    mandatory=True,
                    allowed_issuers=list(allowed_issuers),
                )
            ],
            owner="dev-team",
        ),
    )
    dispatch = devsync_service.dispatch(
        db_session,
        DevSyncDispatchRequest(
            organization_id=ORG,
            finding_id=finding.id,
            remediation_plan_id=plan.id,
        ),
    )
    return plan, dispatch


def test_developer_remediation_through_devsync_callback(db_session):
    _, _, _, decision = _escalated_control_failure(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]

    plan, dispatch = _dispatch_and_plan(db_session, finding)
    payload = json.loads(dispatch.payload)
    # Outbound payload carries the required DevSync data.
    assert payload["finding_id"] == finding.finding_id
    assert payload["source_decision_id"] == decision.id
    assert payload["callback_reference"] == dispatch.callback_reference
    assert payload["severity"] == finding.severity

    # DevSync reports completion and returns valid resolution evidence.
    devsync_service.handle_callback(
        db_session,
        DevSyncCallbackRequest(
            organization_id=ORG,
            callback_reference=dispatch.callback_reference,
            status=DevSyncCallbackStatus.COMPLETED,
            evidence=[
                DevSyncCallbackEvidence(
                    evidence_type="code_fix_attestation",
                    issuer="ci-system",
                    claims={"build": "green", "fix": "applied"},
                )
            ],
        ),
    )

    result = resolution_validation_service.validate(db_session, ORG, finding.id)
    assert result["outcome"] == ResolutionValidationOutcome.VALIDATED.value

    reassessed = reassessment_service.trigger(db_session, ORG, finding.id)
    assert reassessed["reassessed"] is True
    assert reassessed["decision_outcome"] == DecisionOutcome.APPROVED.value


def test_devsync_completion_alone_does_not_resolve_finding(db_session):
    """A DevSync COMPLETED callback without valid evidence never resolves."""
    _, _, _, decision = _escalated_control_failure(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]
    _, dispatch = _dispatch_and_plan(db_session, finding)

    devsync_service.handle_callback(
        db_session,
        DevSyncCallbackRequest(
            organization_id=ORG,
            callback_reference=dispatch.callback_reference,
            status=DevSyncCallbackStatus.COMPLETED,
            evidence=[],
        ),
    )
    result = resolution_validation_service.validate(db_session, ORG, finding.id)
    assert result["outcome"] != ResolutionValidationOutcome.VALIDATED.value
    # CompliAGL retains canonical state: the finding is not CLOSED.
    refreshed = finding_service.get(db_session, ORG, finding.id)
    assert refreshed.status != FindingStatus.CLOSED.value


# --------------------------------------------------------------------------- #
# 3. Invalid resolution evidence
# --------------------------------------------------------------------------- #
def test_invalid_resolution_evidence_rejected(db_session):
    _, _, _, decision = _escalated_control_failure(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]
    remediation_service.create_plan(
        db_session,
        RemediationPlanCreate(
            organization_id=ORG,
            finding_id=finding.id,
            required_resolution_evidence=[
                RequiredResolutionEvidenceModel(
                    evidence_type="code_fix_attestation",
                    mandatory=True,
                    allowed_issuers=["trusted-ci"],
                )
            ],
        ),
    )
    # Evidence from an untrusted issuer fails validation.
    evidence = resolution_evidence_service.submit(
        db_session,
        ResolutionEvidenceSubmit(
            organization_id=ORG,
            finding_id=finding.id,
            evidence_type="code_fix_attestation",
            issuer="rogue-issuer",
            claims={"build": "green"},
        ),
    )
    assert evidence.validation_outcome != "VALID"

    result = resolution_validation_service.validate(db_session, ORG, finding.id)
    assert result["outcome"] == ResolutionValidationOutcome.REJECTED.value

    reassessed = reassessment_service.trigger(db_session, ORG, finding.id)
    assert reassessed["reassessed"] is False


# --------------------------------------------------------------------------- #
# 4. Expired delegation cannot be falsely resolved
# --------------------------------------------------------------------------- #
def test_expired_delegation_cannot_be_falsely_resolved(db_session):
    intent = _mk_intent(db_session)
    resolution_id = "res-" + uuid.uuid4().hex[:8]
    _mk_control_eval(
        db_session,
        resolution_id,
        result=ControlEvaluationOutcome.NOT_SATISFIED.value,
        control_id="CTRL-DELEGATION",
        reasons=("DELEGATION_NOT_SATISFIED",),
    )
    assessment = _mk_assessment(
        db_session, resolution_id, overall_result=AssessmentOutcome.NOT_SATISFIED.value
    )
    decision = _mk_decision(
        db_session,
        intent.id,
        resolution_id,
        assessment.id,
        outcome=DecisionOutcome.ESCALATED.value,
        reason_codes=["DECISION_ESCALATED"],
    )
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]
    remediation_service.create_plan(
        db_session,
        RemediationPlanCreate(
            organization_id=ORG,
            finding_id=finding.id,
            required_resolution_evidence=[
                RequiredResolutionEvidenceModel(
                    evidence_type="delegation_attestation",
                    mandatory=True,
                    allowed_issuers=["identity-provider"],
                )
            ],
        ),
    )
    # An expired delegation attestation must not validate the resolution.
    evidence = resolution_evidence_service.submit(
        db_session,
        ResolutionEvidenceSubmit(
            organization_id=ORG,
            finding_id=finding.id,
            evidence_type="delegation_attestation",
            issuer="identity-provider",
            issued_at=utc_now() - timedelta(days=30),
            expires_at=utc_now() - timedelta(days=1),
            claims={"delegated": True},
        ),
    )
    assert evidence.validation_outcome == "EXPIRED"

    result = resolution_validation_service.validate(db_session, ORG, finding.id)
    assert result["outcome"] == ResolutionValidationOutcome.REJECTED.value

    reassessed = reassessment_service.trigger(db_session, ORG, finding.id)
    assert reassessed["reassessed"] is False
    assert reassessed["new_decision_id"] is None


# --------------------------------------------------------------------------- #
# 5. Terminal prohibition
# --------------------------------------------------------------------------- #
def test_terminal_prohibition_is_not_remediable(db_session):
    intent = _mk_intent(db_session)
    resolution_id = "res-" + uuid.uuid4().hex[:8]
    assessment = _mk_assessment(
        db_session, resolution_id, overall_result=AssessmentOutcome.NOT_SATISFIED.value
    )
    decision = _mk_decision(
        db_session,
        intent.id,
        resolution_id,
        assessment.id,
        outcome=DecisionOutcome.DENIED.value,
        reason_codes=["DECISION_DENIED", "POLICY_PROHIBITION"],
        triggered=[
            {
                "condition_id": "c1",
                "resulting_decision": DecisionOutcome.DENIED.value,
                "terminal": True,
            }
        ],
    )
    findings = finding_service.generate_for_decision(db_session, ORG, decision.id)
    prohibition = next(
        f for f in findings if f.finding_type == FindingType.POLICY_PROHIBITION.value
    )
    assert prohibition.terminal is True
    assert prohibition.remediation_eligibility == RemediationEligibility.INELIGIBLE.value

    # A remediation plan can never be created for a terminal finding.
    with pytest.raises(ConflictError):
        remediation_service.create_plan(
            db_session,
            RemediationPlanCreate(organization_id=ORG, finding_id=prohibition.id),
        )

    # Re-assessment terminates the intent instead of producing a new decision.
    reassessed = reassessment_service.trigger(db_session, ORG, prohibition.id)
    assert reassessed["reassessed"] is False
    refreshed = finding_service.get(db_session, ORG, prohibition.id)
    assert refreshed.status == FindingStatus.TERMINATED.value
    terminated_intent = IntentRepository(db_session).get(ORG, intent.id)
    assert terminated_intent.status == "DENIED"


# --------------------------------------------------------------------------- #
# 6. Prior decision preservation
# --------------------------------------------------------------------------- #
def test_prior_decision_preserved_after_reassessment(db_session):
    _, _, _, decision = _escalated_control_failure(db_session)
    original_outcome = decision.outcome
    original_hash = decision.decision_hash
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]

    _, dispatch = _dispatch_and_plan(db_session, finding)
    devsync_service.handle_callback(
        db_session,
        DevSyncCallbackRequest(
            organization_id=ORG,
            callback_reference=dispatch.callback_reference,
            status=DevSyncCallbackStatus.COMPLETED,
            evidence=[
                DevSyncCallbackEvidence(
                    evidence_type="code_fix_attestation",
                    issuer="ci-system",
                    claims={"build": "green"},
                )
            ],
        ),
    )
    resolution_validation_service.validate(db_session, ORG, finding.id)
    reassessed = reassessment_service.trigger(db_session, ORG, finding.id)

    prior = DecisionRepository(db_session).get(ORG, decision.id)
    # Immutable: outcome and hash unchanged; only supersession metadata updated.
    assert prior.outcome == original_outcome
    assert prior.decision_hash == original_hash
    assert prior.supersession_status == DecisionSupersessionStatus.SUPERSEDED.value
    assert prior.superseded_by_decision_id == reassessed["new_decision_id"]


# --------------------------------------------------------------------------- #
# 7. New decision after re-assessment (+ authorization only for APPROVED)
# --------------------------------------------------------------------------- #
def test_new_decision_after_reassessment_enables_authorization(db_session):
    _, _, _, decision = _escalated_control_failure(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]
    _, dispatch = _dispatch_and_plan(db_session, finding)
    devsync_service.handle_callback(
        db_session,
        DevSyncCallbackRequest(
            organization_id=ORG,
            callback_reference=dispatch.callback_reference,
            status=DevSyncCallbackStatus.COMPLETED,
            evidence=[
                DevSyncCallbackEvidence(
                    evidence_type="code_fix_attestation",
                    issuer="ci-system",
                    claims={"build": "green"},
                )
            ],
        ),
    )
    resolution_validation_service.validate(db_session, ORG, finding.id)
    reassessed = reassessment_service.trigger(db_session, ORG, finding.id)

    new_decision = DecisionRepository(db_session).get(
        ORG, reassessed["new_decision_id"]
    )
    assert new_decision.outcome == DecisionOutcome.APPROVED.value
    assert new_decision.prior_decision_id == decision.id
    assert new_decision.originating_finding_id == finding.id
    assert new_decision.decision_hash != decision.decision_hash

    # Only the new APPROVED decision may produce authorization.
    auth = authorization_service.issue(db_session, ORG, new_decision.id)
    assert auth.decision_id == new_decision.id

    with pytest.raises(ConflictError):
        authorization_service.issue(db_session, ORG, decision.id)


# --------------------------------------------------------------------------- #
# Decision history
# --------------------------------------------------------------------------- #
def test_decision_history_lists_prior_and_new(db_session):
    intent, _, _, decision = _escalated_control_failure(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]
    _, dispatch = _dispatch_and_plan(db_session, finding)
    devsync_service.handle_callback(
        db_session,
        DevSyncCallbackRequest(
            organization_id=ORG,
            callback_reference=dispatch.callback_reference,
            status=DevSyncCallbackStatus.COMPLETED,
            evidence=[
                DevSyncCallbackEvidence(
                    evidence_type="code_fix_attestation",
                    issuer="ci-system",
                    claims={"build": "green"},
                )
            ],
        ),
    )
    resolution_validation_service.validate(db_session, ORG, finding.id)
    reassessment_service.trigger(db_session, ORG, finding.id)

    history = reassessment_service.decision_history(db_session, ORG, intent.id)
    assert len(history["decisions"]) == 2
    outcomes = {d["outcome"] for d in history["decisions"]}
    assert outcomes == {DecisionOutcome.ESCALATED.value, DecisionOutcome.APPROVED.value}
    assert len(history["findings"]) == 1


# --------------------------------------------------------------------------- #
# API surface
# --------------------------------------------------------------------------- #
def _seed_escalated_via_client(db):
    intent, resolution_id, assessment, decision = _escalated_control_failure(db)
    return intent, decision


def test_api_finding_and_remediation_flow(api_client, db_session):
    # Seed a decision + failing control directly in the shared test DB.
    from app.core.database import get_db
    from app.main import app

    # Reuse the api_client's DB session by pulling it from the dependency
    # override so seeded rows are visible to the API.
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        _, decision = _seed_escalated_via_client(db)
    finally:
        db.close()

    headers = {"X-Organization-Id": ORG}

    # Generate findings.
    resp = api_client.post(
        "/api/v1/findings/generate",
        json={"organization_id": ORG, "decision_id": decision.id},
    )
    assert resp.status_code == 201, resp.text
    findings = resp.json()
    assert len(findings) == 1
    finding_id = findings[0]["id"]

    # List + get.
    assert api_client.get("/api/v1/findings", headers=headers).status_code == 200
    assert (
        api_client.get(f"/api/v1/findings/{finding_id}", headers=headers).status_code
        == 200
    )

    # Assign.
    resp = api_client.post(
        f"/api/v1/findings/{finding_id}/assign",
        json={"owner": "dev-team"},
        headers=headers,
    )
    assert resp.json()["status"] == FindingStatus.ASSIGNED.value

    # Remediation plan.
    resp = api_client.post(
        "/api/v1/remediation-plans",
        json={
            "organization_id": ORG,
            "finding_id": finding_id,
            "required_resolution_evidence": [
                {
                    "evidence_type": "code_fix_attestation",
                    "mandatory": True,
                    "allowed_issuers": ["ci-system"],
                }
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    plan_id = resp.json()["id"]

    # Update remediation status.
    resp = api_client.post(
        f"/api/v1/remediation-plans/{plan_id}/status",
        json={"status": "IN_PROGRESS"},
        headers=headers,
    )
    assert resp.json()["status"] == "IN_PROGRESS"

    # DevSync dispatch + callback with valid evidence.
    resp = api_client.post(
        "/api/v1/devsync/dispatch",
        json={
            "organization_id": ORG,
            "finding_id": finding_id,
            "remediation_plan_id": plan_id,
        },
    )
    assert resp.status_code == 201, resp.text
    callback_reference = resp.json()["callback_reference"]

    resp = api_client.post(
        "/api/v1/devsync/callback",
        json={
            "organization_id": ORG,
            "callback_reference": callback_reference,
            "status": "COMPLETED",
            "evidence": [
                {
                    "evidence_type": "code_fix_attestation",
                    "issuer": "ci-system",
                    "claims": {"build": "green"},
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text

    # Validate resolution.
    resp = api_client.post(
        f"/api/v1/findings/{finding_id}/validate-resolution", headers=headers
    )
    assert resp.json()["outcome"] == ResolutionValidationOutcome.VALIDATED.value

    # Trigger re-assessment.
    resp = api_client.post(
        f"/api/v1/findings/{finding_id}/reassess", headers=headers
    )
    body = resp.json()
    assert body["reassessed"] is True
    assert body["decision_outcome"] == DecisionOutcome.APPROVED.value

    # Decision history shows both decisions.
    resp = api_client.get(
        f"/api/v1/decision-history?intent_id={decision.intent_id}", headers=headers
    )
    assert len(resp.json()["decisions"]) == 2


# --------------------------------------------------------------------------- #
# Escalation-approval findings must never reach the re-assessment rubber-stamp
# --------------------------------------------------------------------------- #
# reassessment_service.trigger() hardcodes a SATISFIED assessment + APPROVED
# decision with NO authority check. A decision that escalated for human approval
# (assessment SATISFIED, a policy condition selected ESCALATED -> mapping code
# ESCALATED_BY_POLICY) gets its own finding type so three independent barriers
# keep it out of that path: (1) always remediation-INELIGIBLE, (2) never
# VALIDATED by resolution_validation_service, (3) trigger() refuses it outright.
def _escalated_by_policy(db, *, condition_reason_code="HUMAN_APPROVAL_REQUIRED"):
    """An ESCALATED decision whose escalation came purely from a policy condition."""
    intent = _mk_intent(db)
    resolution_id = "res-" + uuid.uuid4().hex[:8]
    assessment = _mk_assessment(
        db, resolution_id, overall_result=AssessmentOutcome.SATISFIED.value
    )
    decision = _mk_decision(
        db,
        intent.id,
        resolution_id,
        assessment.id,
        outcome=DecisionOutcome.ESCALATED.value,
        reason_codes=[
            "DECISION_ESCALATED",
            "ESCALATED_BY_POLICY",
            condition_reason_code,
        ],
        triggered=[
            {
                "condition_id": "DC-HUMAN-APPROVAL",
                "resulting_decision": "ESCALATED",
                "reason_code": condition_reason_code,
                "priority": 20,
                "terminal": True,
            }
        ],
    )
    return intent, resolution_id, assessment, decision


def test_policy_escalation_produces_escalation_approval_required_finding(db_session):
    _, _, _, decision = _escalated_by_policy(db_session)
    findings = finding_service.generate_for_decision(db_session, ORG, decision.id)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == FindingType.ESCALATION_APPROVAL_REQUIRED.value
    # Barrier 1: never remediable, regardless of package config.
    assert finding.remediation_eligibility == RemediationEligibility.INELIGIBLE.value
    # Not terminal — the intent is recoverable via an authorized approval.
    assert finding.terminal is False
    codes = json.loads(finding.reason_codes)
    assert "FINDING_ESCALATION_APPROVAL_REQUIRED" in codes
    assert "ESCALATED_BY_POLICY" in codes
    assert "HUMAN_APPROVAL_REQUIRED" in codes  # the triggering condition's code


def test_escalation_approval_finding_cannot_get_remediation_plan(db_session):
    _, _, _, decision = _escalated_by_policy(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]
    with pytest.raises(ConflictError):
        remediation_service.create_plan(
            db_session,
            RemediationPlanCreate(
                organization_id=ORG,
                finding_id=finding.id,
                required_corrective_state="n/a",
                required_resolution_evidence=[
                    RequiredResolutionEvidenceModel(
                        evidence_type="code_fix_attestation",
                        mandatory=True,
                        allowed_issuers=["ci-system"],
                    )
                ],
                owner="dev-team",
            ),
        )


def test_escalation_approval_finding_never_validates(db_session):
    _, _, _, decision = _escalated_by_policy(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]

    result = resolution_validation_service.validate(db_session, ORG, finding.id)
    assert result["outcome"] == ResolutionValidationOutcome.REJECTED.value
    assert result["reason_codes"] == ["RESOLUTION_ESCALATION_APPROVAL_PATH_REQUIRED"]

    # Barrier 2 + the evidence trail: the rejection reason is PERSISTED on the
    # finding, not just returned from the call.
    refreshed = finding_service.get(db_session, ORG, finding.id)
    assert refreshed.resolution_validation_outcome == (
        ResolutionValidationOutcome.REJECTED.value
    )
    assert json.loads(refreshed.resolution_reason_codes) == [
        "RESOLUTION_ESCALATION_APPROVAL_PATH_REQUIRED"
    ]
    assert refreshed.status == FindingStatus.VALIDATION_FAILED.value


def test_escalation_approval_finding_blocks_reassessment(db_session):
    _, _, _, decision = _escalated_by_policy(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]

    reassessed = reassessment_service.trigger(db_session, ORG, finding.id)
    assert reassessed["reassessed"] is False
    assert reassessed["reason_codes"] == ["REASSESS_BLOCKED_APPROVAL_PATH_REQUIRED"]
    assert reassessed["new_decision_id"] is None
    assert reassessed["decision_outcome"] is None

    # Barrier 3 + the evidence trail: the block reason is PERSISTED.
    refreshed = finding_service.get(db_session, ORG, finding.id)
    assert json.loads(refreshed.resolution_reason_codes) == [
        "REASSESS_BLOCKED_APPROVAL_PATH_REQUIRED"
    ]
    # No new decision was created for the intent.
    history = reassessment_service.decision_history(db_session, ORG, decision.intent_id)
    assert len(history["decisions"]) == 1
    assert history["decisions"][0]["outcome"] == DecisionOutcome.ESCALATED.value


def test_control_remediation_escalation_is_not_reclassified(db_session):
    """Regression: an assessment-driven (NOT_SATISFIED) escalation keeps its
    CONTROL_FAILURE finding and normal remediable path — only the pure
    policy-condition escalation (ESCALATED_BY_POLICY) gets the new type."""
    _, _, _, decision = _escalated_control_failure(db_session)
    finding = finding_service.generate_for_decision(db_session, ORG, decision.id)[0]
    assert finding.finding_type == FindingType.CONTROL_FAILURE.value
    assert finding.remediation_eligibility == RemediationEligibility.ELIGIBLE.value


# --------------------------------------------------------------------------- #
# EscalationApproval model + repository (commit 2 — persistence wiring only;
# the authority-checked submit path and fact-driven re-decision come next)
# --------------------------------------------------------------------------- #
def _mk_escalation_approval(db, *, decision_id, status=None, **overrides):
    now = utc_now()
    fields = dict(
        organization_id=ORG,
        escalation_approval_id="EAP-" + uuid.uuid4().hex[:16],
        decision_id=decision_id,
        approver_principal_id="principal-jordan",
        approver_principal_type="HUMAN",
        approver_authority_hash="ah-" + uuid.uuid4().hex[:8],
        rationale="Verified approve authority for this action; within policy.",
        granted_at=now,
        valid_until=now + timedelta(seconds=900),
    )
    fields.update(overrides)
    if status is not None:
        fields["status"] = status
    return EscalationApprovalRepository(db).add(EscalationApproval(**fields))


def test_escalation_approval_round_trips_and_defaults_active(db_session):
    intent = _mk_intent(db_session)
    approval = _mk_escalation_approval(
        db_session, decision_id="dec-esc-1", intent_id=intent.id
    )
    assert approval.status == EscalationApprovalStatus.ACTIVE.value
    assert approval.consumed_by_decision_id is None
    fetched = EscalationApprovalRepository(db_session).get(ORG, approval.id)
    assert fetched.approver_principal_type == "HUMAN"
    assert fetched.valid_until > fetched.granted_at


def test_escalation_approval_current_for_decision_only_returns_active(db_session):
    _mk_intent(db_session)
    repo = EscalationApprovalRepository(db_session)
    active = _mk_escalation_approval(db_session, decision_id="dec-esc-2")
    _mk_escalation_approval(
        db_session,
        decision_id="dec-esc-2",
        status=EscalationApprovalStatus.CONSUMED.value,
        consumed_by_decision_id="dec-esc-2-new",
    )
    assert len(repo.list_for_decision(ORG, "dec-esc-2")) == 2
    current = repo.current_for_decision(ORG, "dec-esc-2")
    assert current is not None and current.id == active.id
    assert repo.current_for_decision(ORG, "dec-esc-nonexistent") is None


def test_escalation_approval_ttl_default_is_configured():
    from app.core.config import settings

    assert settings.ESCALATION_APPROVAL_TTL_SECONDS == 900
