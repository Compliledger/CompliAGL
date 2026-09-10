"""Tests for the canonical Deterministic Decision + signed Execution
Authorization stages.

The harness drives the full deterministic pipeline (governance package publish →
policy resolution → applicability → evidence collection → sufficiency → control
evaluation → assessment) and then exercises the Decision stage and the signed
ExecutionAuthorization resource.

Covered scenarios (per the task specification):

* approved decision creates an authorization,
* denied decision cannot create an authorization,
* escalated decision cannot create an authorization,
* expired authorization rejected,
* replay rejected,
* modified target rejected,
* modified amount rejected,
* invalid signature rejected,
* repeated idempotency key returns the original result.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.canonical.actor_identity import ActorIdentityCreate
from app.schemas.canonical.governance_package import (
    ExecutableGovernancePackageCreate,
)
from app.schemas.canonical.intent import IntentCreate
from app.schemas.canonical.operational_context import OperationalContextCreate
from app.schemas.canonical.policy_applicability import (
    ApplicabilityEvaluationCreate,
    PolicyResolutionCreate,
)
from app.schemas.canonical.target import TargetCreate
from app.services.canonical import (
    actor_identity_service,
    applicability_service,
    assessment_service,
    authority_context_service,
    authorization_service,
    control_evaluation_service,
    decision_service,
    evidence_sufficiency_service,
    governance_package_service,
    intent_service,
    operational_context_service,
    policy_resolution_service,
    target_service,
)
from app.services.canonical.authority_context_service import AuthorityContext
from app.services.canonical.errors import ConflictError
from app.services.evidence import evidence_collection_service
from app.services.evidence.connectors import ConnectorRegistry, simulators
from app.utils.canonical_enums import (
    AssessmentOutcome,
    AuthorizationStatus,
    CanonicalActorType,
    DecisionOutcome,
    DecisionSupersessionStatus,
    IntentType,
    TargetType,
)
from app.utils.timestamps import utc_now

ORG = "org-decision"

UTC = timezone.utc
ISSUED = datetime(2025, 1, 1, tzinfo=UTC)
FAR_FUTURE = datetime(2035, 1, 1, tzinfo=UTC)
LONG_FRESH = "P36500D"

EV = "EV-1"
CTL = "CTL-1"


# --------------------------------------------------------------------------- #
# Governance package builder (single mandatory identity control)
# --------------------------------------------------------------------------- #
def _package_payload(
    decision_conditions,
    *,
    control_expression="True",
    requires_authority_context=False,
):
    return ExecutableGovernancePackageCreate(
        organization_id=ORG,
        package_name="decision-policy",
        package_version="1.0.0",
        requires_authority_context=requires_authority_context,
        requirements=[
            {
                "requirement_id": "REQ-1",
                "source_reference": "GEN §1",
                "normalized_text": "The action must satisfy governance evidence.",
                "requirement_type": "generic",
                "classification": "OBLIGATION",
                "mapped_control_ids": [CTL],
                "applicability_criteria": {
                    "op": "equals",
                    "field": "intent.action",
                    "value": "perform_action",
                },
            }
        ],
        control_definitions=[
            {
                "control_id": CTL,
                "requirement_ids": ["REQ-1"],
                "control_objective": "Identity delegation is valid.",
                "evaluation_expression": control_expression,
                "expected_outcome": "APPROVED",
                "mandatory": True,
                "severity": "HIGH",
                "failure_disposition": "DENY",
                "evidence_requirement_ids": [EV],
            }
        ],
        evidence_requirements=[
            {
                "evidence_requirement_id": EV,
                "control_ids": [CTL],
                "evidence_type": "delegation",
                "authoritative_source_type": "identity_provider",
                "subject_binding": "actor",
                "freshness_requirement": LONG_FRESH,
                "validation_method": "signature_verification",
                "allowed_issuers": ["idp.example"],
                "minimum_cardinality": 1,
                "mandatory": True,
            }
        ],
        decision_conditions=decision_conditions,
        metadata={},
    )


def _publish(
    db,
    decision_conditions,
    *,
    control_expression="True",
    requires_authority_context=False,
):
    pkg = governance_package_service.create(
        db,
        _package_payload(
            decision_conditions,
            control_expression=control_expression,
            requires_authority_context=requires_authority_context,
        ),
    )
    result = governance_package_service.validate(db, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(
        db, ORG, pkg.id, approver_principal_id="tester", rationale="approved for test"
    )
    return governance_package_service.publish(db, ORG, pkg.id)


def _identity_fixture(actor_id, *, valid=True):
    return {
        "identity": {
            EV: {
                "issuer": "idp.example",
                "issued_at": ISSUED,
                "expires_at": (
                    FAR_FUTURE if valid else datetime(2020, 1, 1, tzinfo=UTC)
                ),
                "signature": "sig-identity",
                "signature_valid": valid,
                "subject_id": actor_id,
                "claims": {"delegation": "granted", "scope": "perform_action"},
            }
        }
    }


def _registry(fixtures) -> ConnectorRegistry:
    return ConnectorRegistry(
        [
            simulators.identity_delegation_connector(
                fixtures=fixtures["identity"], is_mock=True
            )
        ]
    )


def _run_pipeline(
    db,
    decision_conditions,
    *,
    evidence_valid=True,
    control_expression="True",
    requires_authority_context=False,
):
    """Publish, resolve, collect + evaluate, and return (resolution, actor,
    target, assessment)."""
    _publish(
        db,
        decision_conditions,
        control_expression=control_expression,
        requires_authority_context=requires_authority_context,
    )
    actor = actor_identity_service.create(
        db,
        ActorIdentityCreate(
            organization_id=ORG,
            actor_type=CanonicalActorType.AI_AGENT,
            # Gives _authority_principal_id a real value to map to, so the
            # authority-context tests below actually reach the (fake) client
            # instead of short-circuiting on a missing principal id.
            wallet_or_agent_account_id="agent-01",
        ),
    )
    intent = intent_service.create(
        db,
        IntentCreate(
            organization_id=ORG,
            intent_type=IntentType.PAYMENT,
            action="perform_action",
            actor_id=actor.id,
            amount_minor=25000,
            amount_currency="USD",
        ),
    )
    target = target_service.create(
        db,
        TargetCreate(
            organization_id=ORG,
            target_type=TargetType.MERCHANT,
            external_identifier="counterparty-01",
        ),
    )
    context = operational_context_service.create(
        db,
        OperationalContextCreate(
            organization_id=ORG, jurisdiction="US", environment="STAGING"
        ),
    )
    resolution = policy_resolution_service.resolve(
        db,
        PolicyResolutionCreate(
            organization_id=ORG,
            actor_identity_id=actor.id,
            intent_id=intent.id,
            target_id=target.id,
            operational_context_id=context.id,
        ),
    )
    applicability_service.evaluate_for_resolution(
        db,
        ApplicabilityEvaluationCreate(
            organization_id=ORG, policy_resolution_id=resolution.id
        ),
    )
    evidence_collection_service.start_collection(
        db,
        ORG,
        resolution.id,
        production_mode=False,
        registry=_registry(_identity_fixture(actor.id, valid=evidence_valid)),
    )
    evidence_sufficiency_service.evaluate_for_resolution(db, ORG, resolution.id)
    control_evaluation_service.evaluate_for_resolution(db, ORG, resolution.id)
    assessment = assessment_service.assess_for_resolution(db, ORG, resolution.id)
    return resolution, actor, target, assessment


_APPROVE_CONDITIONS = [
    {
        "condition_id": "DC-APPROVE",
        "expression": "True",
        "resulting_decision": "APPROVED",
        "priority": 100,
        "reason_code": "APPROVED_OK",
        "terminal": True,
    }
]
_DENY_CONDITIONS = [
    {
        "condition_id": "DC-DENY",
        "expression": "intent.action == 'perform_action'",
        "resulting_decision": "DENIED",
        "priority": 10,
        "reason_code": "ACTION_PROHIBITED",
        "terminal": True,
    }
]
_ESCALATE_CONDITIONS = [
    {
        "condition_id": "DC-ESCALATE",
        "expression": "intent.action == 'perform_action'",
        "resulting_decision": "ESCALATED",
        "priority": 10,
        "reason_code": "NEEDS_REVIEW",
        "terminal": True,
    }
]


def _approved_decision(db):
    resolution, actor, target, assessment = _run_pipeline(
        db, _APPROVE_CONDITIONS
    )
    assert assessment.overall_result == AssessmentOutcome.SATISFIED.value
    decision = decision_service.decide_for_resolution(db, ORG, resolution.id)
    assert decision.outcome == DecisionOutcome.APPROVED.value
    return decision


# --------------------------------------------------------------------------- #
# Decision stage
# --------------------------------------------------------------------------- #
def test_approved_decision_creates_authorization(db_session):
    decision = _approved_decision(db_session)
    auth = authorization_service.issue(db_session, ORG, decision.id)

    assert auth.status == AuthorizationStatus.ISSUED.value
    assert auth.decision_id == decision.id
    assert auth.authorized_action == "perform_action"
    assert auth.signature and auth.authorization_hash and auth.signer_key_id
    assert auth.nonce and auth.one_time_use is True
    # The authorization binds the decision it derived from.
    assert auth.decision_hash == decision.decision_hash
    # External systems can independently verify it.
    result = authorization_service.verify(db_session, ORG, auth.id)
    assert result["valid"] is True
    assert result["signature_valid"] is True


def test_denied_decision_cannot_create_authorization(db_session):
    resolution, actor, target, assessment = _run_pipeline(
        db_session, _DENY_CONDITIONS
    )
    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    assert decision.outcome == DecisionOutcome.DENIED.value

    with pytest.raises(ConflictError):
        authorization_service.issue(db_session, ORG, decision.id)


def test_escalated_decision_cannot_create_authorization(db_session):
    resolution, actor, target, assessment = _run_pipeline(
        db_session, _ESCALATE_CONDITIONS
    )
    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    assert decision.outcome == DecisionOutcome.ESCALATED.value

    with pytest.raises(ConflictError):
        authorization_service.issue(db_session, ORG, decision.id)


def test_not_evaluable_assessment_never_approved(db_session):
    # An approving decision condition cannot approve a NOT_EVALUABLE assessment.
    resolution, actor, target, assessment = _run_pipeline(
        db_session,
        _APPROVE_CONDITIONS,
        evidence_valid=False,  # invalid evidence -> control NOT_SATISFIED
    )
    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    assert decision.outcome != DecisionOutcome.APPROVED.value


# Safety-invariant regression test (three distinct ways a mandatory control
# can fail to be affirmatively satisfied):
#
# * "control_not_satisfied"   -- sufficient, valid evidence, but the control's
#   own evaluation_expression evaluates to False.
# * "control_not_evaluable"   -- the control's evaluation_expression cannot be
#   evaluated at all (raises inside the deterministic interpreter -- e.g. an
#   unsupported construct -- which control_evaluation_service maps to
#   NOT_EVALUABLE / CONTROL_EXPRESSION_ERROR rather than silently passing).
# * "mandatory_evidence_invalid" -- the control's expression is trivially true,
#   but its mandatory evidence requirement is backed by invalid evidence
#   (bad signature, expired), which gates the control to NOT_SATISFIED before
#   the expression is ever evaluated.
#
# In every case the governing policy's decision condition is
# `_APPROVE_CONDITIONS`: an unconditional `"True"` that, taken alone, would
# resolve to APPROVED on every request. The point of this test is that a
# failing/unevaluable mandatory control must override that regardless.
@pytest.mark.parametrize(
    (
        "run_kwargs",
        "expected_assessment_outcome",
        "expected_decision_outcome",
        "expected_reason_code",
    ),
    [
        pytest.param(
            {"control_expression": "False"},
            AssessmentOutcome.NOT_SATISFIED.value,
            DecisionOutcome.DENIED.value,
            "MANDATORY_CONTROL_FAILED",
            id="control_not_satisfied",
        ),
        pytest.param(
            {"control_expression": "len(evidence)"},
            AssessmentOutcome.NOT_EVALUABLE.value,
            DecisionOutcome.ESCALATED.value,
            "ASSESSMENT_NOT_EVALUABLE",
            id="control_not_evaluable",
        ),
        pytest.param(
            {"evidence_valid": False},
            AssessmentOutcome.NOT_SATISFIED.value,
            DecisionOutcome.DENIED.value,
            "MANDATORY_CONTROL_FAILED",
            id="mandatory_evidence_invalid",
        ),
    ],
)
def test_mandatory_control_failure_overrides_approving_condition(
    db_session,
    run_kwargs,
    expected_assessment_outcome,
    expected_decision_outcome,
    expected_reason_code,
):
    resolution, actor, target, assessment = _run_pipeline(
        db_session, _APPROVE_CONDITIONS, **run_kwargs
    )
    assert assessment.overall_result == expected_assessment_outcome

    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    explanation = decision_service.explain(db_session, ORG, decision.id)

    # The would-be-approving condition still matched and is recorded as
    # triggered -- proving the override happened, not that the condition was
    # skipped or somehow failed to match.
    triggered = explanation["decision_conditions_triggered"]
    assert any(
        c.get("condition_id") == "DC-APPROVE"
        and c.get("resulting_decision") == DecisionOutcome.APPROVED.value
        for c in triggered
    )

    assert decision.outcome != DecisionOutcome.APPROVED.value
    assert decision.outcome == expected_decision_outcome
    assert expected_reason_code in explanation["reason_codes"]


def test_decision_is_immutable_reevaluation_supersedes(db_session):
    resolution, actor, target, assessment = _run_pipeline(
        db_session, _APPROVE_CONDITIONS
    )
    first = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    second = decision_service.decide_for_resolution(db_session, ORG, resolution.id)

    assert first.id != second.id
    db_session.refresh(first)
    assert (
        first.supersession_status
        == DecisionSupersessionStatus.SUPERSEDED.value
    )
    assert first.superseded_by_decision_id == second.id
    assert (
        second.supersession_status
        == DecisionSupersessionStatus.CURRENT.value
    )
    assert second.prior_decision_id == first.id
    # Deterministic: the two decisions share the same input hash.
    assert first.input_hash == second.input_hash


# A policy that escalates for remediation while unsatisfied and approves once
# the assessment becomes SATISFIED -- lets the SAME decision-condition set
# produce different outcomes as the *assessment* changes, rather than baking
# the outcome into a fixed condition (which wouldn't exercise recomputation).
_REMEDIATION_CONDITIONS = [
    {
        "condition_id": "DC-APPROVE-IF-SATISFIED",
        "expression": "assessment.overall_result == 'SATISFIED'",
        "resulting_decision": "APPROVED",
        "priority": 100,
        "reason_code": "APPROVED_OK",
        "terminal": True,
    },
    {
        "condition_id": "DC-ESCALATE-FOR-REMEDIATION",
        "expression": "assessment.overall_result != 'SATISFIED'",
        "resulting_decision": "ESCALATED",
        "priority": 200,
        "reason_code": "NEEDS_REMEDIATION",
        "terminal": True,
    },
]


def test_decide_recomputes_after_evidence_is_corrected(db_session):
    """Regression test for the "cache by existence, not by input identity" bug:
    a decide() call made while evidence is still invalid must not permanently
    pin the policy_resolution_id to that result. Once evidence collection is
    corrected and rerun for the SAME policy_resolution_id, a later decide()
    must reflect the corrected state (APPROVED), not repeat the first,
    now-stale ESCALATED outcome.
    """
    _publish(db_session, _REMEDIATION_CONDITIONS)
    actor = actor_identity_service.create(
        db_session,
        ActorIdentityCreate(
            organization_id=ORG, actor_type=CanonicalActorType.AI_AGENT
        ),
    )
    intent = intent_service.create(
        db_session,
        IntentCreate(
            organization_id=ORG,
            intent_type=IntentType.PAYMENT,
            action="perform_action",
            actor_id=actor.id,
            amount_minor=25000,
            amount_currency="USD",
        ),
    )
    target = target_service.create(
        db_session,
        TargetCreate(
            organization_id=ORG,
            target_type=TargetType.MERCHANT,
            external_identifier="counterparty-01",
        ),
    )
    context = operational_context_service.create(
        db_session,
        OperationalContextCreate(
            organization_id=ORG, jurisdiction="US", environment="STAGING"
        ),
    )
    resolution = policy_resolution_service.resolve(
        db_session,
        PolicyResolutionCreate(
            organization_id=ORG,
            actor_identity_id=actor.id,
            intent_id=intent.id,
            target_id=target.id,
            operational_context_id=context.id,
        ),
    )
    applicability_service.evaluate_for_resolution(
        db_session,
        ApplicabilityEvaluationCreate(
            organization_id=ORG, policy_resolution_id=resolution.id
        ),
    )

    # Pass 1: invalid evidence -> control NOT_SATISFIED -> assessment
    # NOT_SATISFIED -> policy escalates for remediation.
    evidence_collection_service.start_collection(
        db_session,
        ORG,
        resolution.id,
        production_mode=False,
        registry=_registry(_identity_fixture(actor.id, valid=False)),
    )
    first = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    assert first.outcome == DecisionOutcome.ESCALATED.value

    # Evidence is corrected and evidence collection is re-run for the SAME
    # policy_resolution_id.
    evidence_collection_service.start_collection(
        db_session,
        ORG,
        resolution.id,
        production_mode=False,
        registry=_registry(_identity_fixture(actor.id, valid=True)),
    )
    second = decision_service.decide_for_resolution(db_session, ORG, resolution.id)

    assert second.outcome == DecisionOutcome.APPROVED.value
    # A genuinely new assessment was computed from the corrected evidence --
    # not the first (stale) assessment reused unconditionally.
    assert second.assessment_id != first.assessment_id


def test_decision_records_full_binding(db_session):
    decision = _approved_decision(db_session)
    explanation = decision_service.explain(db_session, ORG, decision.id)
    assert explanation["result"] == DecisionOutcome.APPROVED.value
    assert explanation["assessment_id"]
    assert explanation["control_evaluation_ids"]
    assert explanation["applicable_package_ids"]
    assert explanation["decision_conditions_triggered"]
    assert decision.decision_hash and decision.input_hash


# --------------------------------------------------------------------------- #
# Execution Authorization
# --------------------------------------------------------------------------- #
def test_expired_authorization_rejected(db_session):
    decision = _approved_decision(db_session)
    auth = authorization_service.issue(
        db_session,
        ORG,
        decision.id,
        expires_at=datetime(2020, 1, 1, tzinfo=UTC),  # already in the past
    )
    result = authorization_service.verify(db_session, ORG, auth.id)
    assert result["valid"] is False
    assert "AUTHORIZATION_EXPIRED" in result["reasons"]

    with pytest.raises(ConflictError):
        authorization_service.consume(db_session, ORG, auth.id)


def test_replay_rejected(db_session):
    decision = _approved_decision(db_session)
    auth = authorization_service.issue(db_session, ORG, decision.id)

    consumed = authorization_service.consume(db_session, ORG, auth.id)
    assert consumed.status == AuthorizationStatus.CONSUMED.value
    assert consumed.consumed_at is not None

    # A second consume (replay) is rejected.
    with pytest.raises(ConflictError):
        authorization_service.consume(db_session, ORG, auth.id)

    # Verification of a consumed authorization is invalid.
    result = authorization_service.verify(db_session, ORG, auth.id)
    assert result["valid"] is False
    assert "AUTHORIZATION_ALREADY_CONSUMED" in result["reasons"]


def test_modified_target_rejected(db_session):
    decision = _approved_decision(db_session)
    auth = authorization_service.issue(db_session, ORG, decision.id)

    # The correct target passes bound-field verification.
    ok = authorization_service.verify(
        db_session, ORG, auth.id, expected_fields={"target_id": auth.target_id}
    )
    assert ok["valid"] is True

    # A modified target is rejected.
    bad = authorization_service.verify(
        db_session,
        ORG,
        auth.id,
        expected_fields={"target_id": "some-other-target"},
    )
    assert bad["valid"] is False
    assert "BOUND_FIELD_MISMATCH" in bad["reasons"]
    assert "target_id" in bad["mismatched_fields"]


def test_modified_amount_rejected(db_session):
    decision = _approved_decision(db_session)
    auth = authorization_service.issue(db_session, ORG, decision.id)

    bad = authorization_service.verify(
        db_session,
        ORG,
        auth.id,
        expected_fields={"max_amount_minor": auth.max_amount_minor + 1},
    )
    assert bad["valid"] is False
    assert "BOUND_FIELD_MISMATCH" in bad["reasons"]
    assert "max_amount_minor" in bad["mismatched_fields"]


def test_invalid_signature_rejected(db_session):
    decision = _approved_decision(db_session)
    auth = authorization_service.issue(db_session, ORG, decision.id)

    # Tamper with the stored signature.
    auth.signature = "deadbeef" * 8
    db_session.commit()

    result = authorization_service.verify(db_session, ORG, auth.id)
    assert result["valid"] is False
    assert result["signature_valid"] is False
    assert "INVALID_SIGNATURE" in result["reasons"]

    with pytest.raises(ConflictError):
        authorization_service.consume(db_session, ORG, auth.id)


def test_repeated_idempotency_key_returns_original(db_session):
    decision = _approved_decision(db_session)
    first = authorization_service.issue(
        db_session, ORG, decision.id, idempotency_key="idem-123"
    )
    second = authorization_service.issue(
        db_session, ORG, decision.id, idempotency_key="idem-123"
    )
    assert first.id == second.id
    assert first.nonce == second.nonce
    assert first.authorization_hash == second.authorization_hash


def test_tampered_bound_field_breaks_hash(db_session):
    # If a persisted bound field is tampered with, the recomputed hash no longer
    # matches and verification fails even though the signature covers the old
    # hash.
    decision = _approved_decision(db_session)
    auth = authorization_service.issue(db_session, ORG, decision.id)

    auth.max_amount_minor = (auth.max_amount_minor or 0) + 999
    db_session.commit()

    result = authorization_service.verify(db_session, ORG, auth.id)
    assert result["valid"] is False
    assert result["hash_valid"] is False
    assert "AUTHORIZATION_HASH_MISMATCH" in result["reasons"]


def test_revoked_authorization_rejected(db_session):
    decision = _approved_decision(db_session)
    auth = authorization_service.issue(db_session, ORG, decision.id)

    revoked = authorization_service.revoke(
        db_session, ORG, auth.id, reason="manual"
    )
    assert revoked.status == AuthorizationStatus.REVOKED.value
    assert revoked.revoked_at is not None

    result = authorization_service.verify(db_session, ORG, auth.id)
    assert result["valid"] is False
    assert "AUTHORIZATION_REVOKED" in result["reasons"]

    with pytest.raises(ConflictError):
        authorization_service.consume(db_session, ORG, auth.id)


def test_verify_activates_issued_authorization(db_session):
    decision = _approved_decision(db_session)
    auth = authorization_service.issue(db_session, ORG, decision.id)
    assert auth.status == AuthorizationStatus.ISSUED.value

    result = authorization_service.verify(db_session, ORG, auth.id)
    assert result["valid"] is True
    db_session.refresh(auth)
    assert auth.status == AuthorizationStatus.ACTIVE.value


# --------------------------------------------------------------------------- #
# API surface (end-to-end over HTTP)
# --------------------------------------------------------------------------- #
@pytest.fixture()
def api_env():
    """Yield a TestClient plus a session bound to the *same* in-memory DB.

    This lets a test drive the canonical pipeline through the service layer and
    then exercise the Decision / ExecutionAuthorization HTTP routes against the
    same data.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    db = Session()
    try:
        yield TestClient(app), db
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_api_decision_and_authorization_flow(api_env):
    client, db = api_env
    headers = {"X-Organization-Id": ORG}

    resolution, actor, target, assessment = _run_pipeline(db, _APPROVE_CONDITIONS)
    db.commit()

    # Run the deterministic decision engine over HTTP.
    resp = client.post(
        "/api/v1/decisions/decide",
        json={"organization_id": ORG, "policy_resolution_id": resolution.id},
    )
    assert resp.status_code == 201, resp.text
    decision = resp.json()
    assert decision["outcome"] == DecisionOutcome.APPROVED.value

    # Retrieve + explain the decision.
    got = client.get(f"/api/v1/decisions/{decision['id']}", headers=headers)
    assert got.status_code == 200
    explained = client.get(
        f"/api/v1/decisions/{decision['id']}/explain", headers=headers
    )
    assert explained.status_code == 200
    assert explained.json()["result"] == DecisionOutcome.APPROVED.value

    # Issue a signed authorization.
    issued = client.post(
        "/api/v1/execution-authorizations/issue",
        json={"organization_id": ORG, "decision_id": decision["id"]},
    )
    assert issued.status_code == 201, issued.text
    auth = issued.json()
    assert auth["status"] == AuthorizationStatus.ISSUED.value
    assert auth["signature"] and auth["authorization_hash"]

    # Independently verify it (activates ISSUED -> ACTIVE).
    verified = client.post(
        f"/api/v1/execution-authorizations/{auth['id']}/verify",
        json={},
        headers=headers,
    )
    assert verified.status_code == 200
    assert verified.json()["valid"] is True

    # Consume it once; replay is rejected.
    consumed = client.post(
        f"/api/v1/execution-authorizations/{auth['id']}/consume", headers=headers
    )
    assert consumed.status_code == 200
    assert consumed.json()["status"] == AuthorizationStatus.CONSUMED.value

    replay = client.post(
        f"/api/v1/execution-authorizations/{auth['id']}/consume", headers=headers
    )
    assert replay.status_code == 409


# --------------------------------------------------------------------------- #
# CompliIdentity authority-context integration
# --------------------------------------------------------------------------- #
_AUTHORITY_ESCALATE_CONDITIONS = [
    {
        "condition_id": "DC-AUTHORITY-ESCALATE",
        "expression": "authority.reason == 'approval_required'",
        "resulting_decision": "ESCALATED",
        "priority": 10,
        "reason_code": "HUMAN_APPROVAL_REQUIRED",
        "terminal": True,
    },
    {
        "condition_id": "DC-APPROVE",
        "expression": "True",
        "resulting_decision": "APPROVED",
        "priority": 100,
        "reason_code": "APPROVED_OK",
        "terminal": True,
    },
]
_AUTHORITY_DENY_CONDITIONS = [
    {
        "condition_id": "DC-AUTHORITY-DENY",
        "expression": "authority.reason == 'principal_not_found'",
        "resulting_decision": "DENIED",
        "priority": 10,
        "reason_code": "PRINCIPAL_NOT_FOUND",
        "terminal": True,
    },
    {
        "condition_id": "DC-APPROVE",
        "expression": "True",
        "resulting_decision": "APPROVED",
        "priority": 100,
        "reason_code": "APPROVED_OK",
        "terminal": True,
    },
]


class _FakeAuthorityClient:
    """Stands in for authority_context_service.AuthorityContextClient in
    tests -- no real CompliIdentity is reachable from this test suite."""

    def __init__(self, context: AuthorityContext):
        self._context = context

    def fetch(self, **kwargs):
        return self._context


def _patch_authority_client(monkeypatch, context: AuthorityContext) -> None:
    monkeypatch.setattr(
        authority_context_service,
        "default_client",
        lambda **kwargs: _FakeAuthorityClient(context),
    )


def test_package_without_authority_requirement_never_calls_compliidentity(
    db_session, monkeypatch
):
    """Packages that don't set requires_authority_context must be completely
    unaffected by this integration -- not even a client lookup happens. This
    is what keeps the existing demo travel-booking package and every other
    test in this suite unmodified by the integration's existence."""

    def _boom(**kwargs):
        raise AssertionError(
            "authority_context_service.default_client() must not be called "
            "when the governing package didn't set requires_authority_context"
        )

    monkeypatch.setattr(authority_context_service, "default_client", _boom)

    decision = _approved_decision(db_session)
    assert decision.authority_status is None
    assert decision.authority_reason is None
    assert decision.authority_hash is None


def test_authority_context_unconfigured_forces_escalation_over_approval(
    db_session,
):
    """requires_authority_context=True with CompliIdentity unconfigured in
    this test environment (no COMPLIIDENTITY_BASE_URL /
    COMPLIIDENTITY_SERVICE_PRINCIPAL_ID) must fail closed: an
    otherwise-unconditionally-approving decision condition is downgraded to
    ESCALATED, never APPROVED. No monkeypatching -- this is the real
    default_client() behavior when unconfigured."""
    resolution, actor, target, assessment = _run_pipeline(
        db_session, _APPROVE_CONDITIONS, requires_authority_context=True
    )
    assert assessment.overall_result == AssessmentOutcome.SATISFIED.value

    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    explanation = decision_service.explain(db_session, ORG, decision.id)

    # The approving condition still matched and is recorded as triggered --
    # proving the override happened, not that the condition failed to match.
    triggered = explanation["decision_conditions_triggered"]
    assert any(
        c.get("condition_id") == "DC-APPROVE"
        and c.get("resulting_decision") == DecisionOutcome.APPROVED.value
        for c in triggered
    )

    assert decision.outcome == DecisionOutcome.ESCALATED.value
    assert "AUTHORITY_CONTEXT_UNAVAILABLE" in explanation["reason_codes"]
    assert decision.authority_status == "UNAVAILABLE"
    assert decision.authority_hash is not None


def test_authority_context_unavailable_from_client_also_overrides_approval(
    db_session, monkeypatch
):
    """Same guarantee, but via a client that IS configured/reachable and
    still reports UNAVAILABLE -- e.g. CompliIdentity's own 503
    context_unevaluable fail-closed response -- not just the unconfigured
    path above."""
    _patch_authority_client(
        monkeypatch,
        AuthorityContext(status="UNAVAILABLE", reason="context_unevaluable"),
    )
    resolution, actor, target, assessment = _run_pipeline(
        db_session, _APPROVE_CONDITIONS, requires_authority_context=True
    )
    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)

    assert decision.outcome == DecisionOutcome.ESCALATED.value
    assert decision.authority_status == "UNAVAILABLE"
    assert decision.authority_reason == "context_unevaluable"


def test_authority_context_approval_required_reason_drives_package_condition(
    db_session, monkeypatch
):
    """A successful CompliIdentity call whose authority_for_request.reason is
    'approval_required' is exposed as an ordinary package-authorable fact
    (authority.reason) -- the package's own decision condition, not engine
    logic, is what turns it into ESCALATED."""
    _patch_authority_client(
        monkeypatch,
        AuthorityContext(
            status="OK",
            reason="approval_required",
            sufficient=False,
            active=True,
            current_trust_state={"present": True, "fail_closed": False},
            authority_revision="rev-1",
        ),
    )
    resolution, actor, target, assessment = _run_pipeline(
        db_session,
        _AUTHORITY_ESCALATE_CONDITIONS,
        requires_authority_context=True,
    )
    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    explanation = decision_service.explain(db_session, ORG, decision.id)

    assert decision.outcome == DecisionOutcome.ESCALATED.value
    assert "HUMAN_APPROVAL_REQUIRED" in explanation["reason_codes"]
    assert decision.authority_status == "OK"
    assert decision.authority_reason == "approval_required"


def test_authority_context_known_denied_drives_package_deny_condition(
    db_session, monkeypatch
):
    """KNOWN_DENIED (e.g. 404 principal_not_found) is a real fact
    CompliIdentity reported, not a system failure -- it must NOT trigger the
    structural UNAVAILABLE guard, and is instead handled the same way as any
    other authority.reason: via a package-authored condition."""
    _patch_authority_client(
        monkeypatch,
        AuthorityContext(status="KNOWN_DENIED", reason="principal_not_found"),
    )
    resolution, actor, target, assessment = _run_pipeline(
        db_session,
        _AUTHORITY_DENY_CONDITIONS,
        requires_authority_context=True,
    )
    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    explanation = decision_service.explain(db_session, ORG, decision.id)

    assert decision.outcome == DecisionOutcome.DENIED.value
    assert "PRINCIPAL_NOT_FOUND" in explanation["reason_codes"]
    assert decision.authority_status == "KNOWN_DENIED"


def test_authority_context_ok_allows_approval_when_package_requires_it(
    db_session, monkeypatch
):
    """The structural guard only fires on UNAVAILABLE -- a successful
    authority context does not block an otherwise-approving decision."""
    _patch_authority_client(
        monkeypatch,
        AuthorityContext(
            status="OK",
            sufficient=True,
            active=True,
            current_trust_state={"present": True, "fail_closed": False},
        ),
    )
    resolution, actor, target, assessment = _run_pipeline(
        db_session, _APPROVE_CONDITIONS, requires_authority_context=True
    )
    assert assessment.overall_result == AssessmentOutcome.SATISFIED.value

    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    assert decision.outcome == DecisionOutcome.APPROVED.value
    assert decision.authority_status == "OK"


_AUTHORITY_BOOLEAN_FACT_CONDITIONS = [
    {
        "condition_id": "DC-APPROVAL-REQUIRED-BOOL",
        # keys off CompliIdentity's own boolean, not the derived reason
        "expression": "authority.approval_required == True",
        "resulting_decision": "ESCALATED",
        "priority": 10,
        "reason_code": "HUMAN_APPROVAL_REQUIRED",
        "terminal": True,
    },
    {
        "condition_id": "DC-APPROVE",
        "expression": "True",
        "resulting_decision": "APPROVED",
        "priority": 100,
        "reason_code": "APPROVED_OK",
        "terminal": True,
    },
]


def _fake_intent(parameters=None, *, intent_type="transfer", amount_minor=None):
    import json as _json
    from types import SimpleNamespace

    return SimpleNamespace(
        parameters=_json.dumps(parameters) if parameters is not None else None,
        intent_type=intent_type,
        amount_minor=amount_minor,
    )


def test_authority_request_params_defaults_unchanged():
    """A package that supplies none of the compliidentity_* params probes
    exactly as before: generic 'request' verb, intent_type as resource, no
    resource_instance."""
    params = decision_service._authority_request_params(_fake_intent())
    assert params == {"resource": "transfer", "action": "request"}


def test_authority_request_params_semantic_action_and_instance():
    intent = _fake_intent(
        {
            "compliidentity_resource": "aml.action",
            "compliidentity_action": "propose",
            "compliidentity_resource_instance": "HARBORSTONE-2024-0042",
        },
        amount_minor=25000000,
    )
    params = decision_service._authority_request_params(intent)
    assert params == {
        "resource": "aml.action",
        "action": "propose",
        "resource_instance": "HARBORSTONE-2024-0042",
        "attribute": "amount",
        "value": "25000000",
    }


def test_authority_request_params_partial_opt_in():
    """Supplying only the action still leaves resource_instance unsent."""
    intent = _fake_intent({"compliidentity_action": "approve"})
    params = decision_service._authority_request_params(intent)
    assert params == {"resource": "transfer", "action": "approve"}
    assert "resource_instance" not in params


def test_authority_structured_booleans_exposed_as_facts(db_session, monkeypatch):
    """The raw authority_for_request booleans (approval_required here) reach
    package conditions as facts independently of the derived `authority.reason`
    -- proves runtime_facts.build_authority_facts wiring, not just parsing."""
    _patch_authority_client(
        monkeypatch,
        AuthorityContext(
            status="OK",
            reason=None,  # deliberately not set -- the boolean must stand alone
            sufficient=False,
            active=True,
            approval_required=True,
            findings=("permission_present", "approval_required"),
        ),
    )
    resolution, actor, target, assessment = _run_pipeline(
        db_session,
        _AUTHORITY_BOOLEAN_FACT_CONDITIONS,
        requires_authority_context=True,
    )
    decision = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    explanation = decision_service.explain(db_session, ORG, decision.id)

    assert decision.outcome == DecisionOutcome.ESCALATED.value
    assert "HUMAN_APPROVAL_REQUIRED" in explanation["reason_codes"]


def test_api_issue_rejected_for_denied_decision(api_env):
    client, db = api_env

    resolution, actor, target, assessment = _run_pipeline(db, _DENY_CONDITIONS)
    db.commit()

    resp = client.post(
        "/api/v1/decisions/decide",
        json={"organization_id": ORG, "policy_resolution_id": resolution.id},
    )
    assert resp.status_code == 201
    decision = resp.json()
    assert decision["outcome"] == DecisionOutcome.DENIED.value

    issued = client.post(
        "/api/v1/execution-authorizations/issue",
        json={"organization_id": ORG, "decision_id": decision["id"]},
    )
    assert issued.status_code == 409
