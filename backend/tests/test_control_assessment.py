"""Tests for the Evidence Sufficiency, Control Evaluation and Assessment stages.

These three deterministic stages run after evidence collection and before the
Decision stage. The tests exercise the required scenarios:

* all controls satisfied,
* one mandatory control not satisfied,
* optional control failure,
* stale evidence making a control not evaluable,
* manual approval requirement,
* deterministic replay,
* assessment separate from decision,
* raw intent assertions cannot satisfy controls without normalized evidence.

The harness reuses the platform-neutral simulator connectors from the evidence
layer so the full chain (collection → normalization → sufficiency → control
evaluation → assessment) is exercised end to end.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

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
    control_evaluation_service,
    evidence_sufficiency_service,
    governance_package_service,
    intent_service,
    operational_context_service,
    policy_resolution_service,
    target_service,
)
from app.services.evidence import evidence_collection_service
from app.services.evidence.connectors import ConnectorRegistry, simulators
from app.utils.canonical_enums import (
    AssessmentOutcome,
    CanonicalActorType,
    ControlEvaluationOutcome,
    DecisionOutcome,
    EvidenceRequirementSufficiency,
    EvidenceSufficiencyOutcome,
    IntentType,
    TargetType,
)
from app.utils.timestamps import utc_now

ORG = "org-assessment"

UTC = timezone.utc
ISSUED = datetime(2025, 1, 1, tzinfo=UTC)
FAR_FUTURE = datetime(2035, 1, 1, tzinfo=UTC)
PAST = datetime(2020, 1, 1, tzinfo=UTC)
LONG_FRESH = "P36500D"

EV_IDENTITY = "EV-IDENTITY"
EV_ALLOWANCE = "EV-ALLOWANCE"
EV_APPROVAL = "EV-APPROVAL"
EV_MERCHANT = "EV-MERCHANT"
EV_EXECUTION = "EV-EXECUTION"

CTL_IDENTITY = "CTL-IDENTITY"
CTL_ALLOWANCE = "CTL-ALLOWANCE"
CTL_APPROVAL = "CTL-APPROVAL"
CTL_MERCHANT = "CTL-MERCHANT"
CTL_EXECUTION = "CTL-EXECUTION"

_CONTROL_EVIDENCE = {
    CTL_IDENTITY: EV_IDENTITY,
    CTL_ALLOWANCE: EV_ALLOWANCE,
    CTL_APPROVAL: EV_APPROVAL,
    CTL_MERCHANT: EV_MERCHANT,
    CTL_EXECUTION: EV_EXECUTION,
}


# --------------------------------------------------------------------------- #
# Governance package builder (platform-neutral, configurable)
# --------------------------------------------------------------------------- #
def _requirements() -> list[dict]:
    return [
        {
            "requirement_id": "REQ-MAIN",
            "source_reference": "GEN §1",
            "normalized_text": "The action must satisfy governance evidence.",
            "requirement_type": "generic",
            "classification": "OBLIGATION",
            "mapped_control_ids": list(_CONTROL_EVIDENCE.keys()),
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.action",
                "value": "perform_action",
            },
        }
    ]


def _controls(control_overrides: dict) -> list[dict]:
    out = []
    for cid, ev in _CONTROL_EVIDENCE.items():
        overrides = control_overrides.get(cid, {})
        out.append(
            {
                "control_id": cid,
                "requirement_ids": ["REQ-MAIN"],
                "control_objective": f"Objective for {cid}.",
                "evaluation_expression": overrides.get(
                    "evaluation_expression", "True"
                ),
                "expected_outcome": "APPROVED",
                "mandatory": overrides.get("mandatory", True),
                "severity": "HIGH",
                "failure_disposition": "DENY",
                "evidence_requirement_ids": [ev],
            }
        )
    return out


def _evidence(evidence_overrides: dict) -> list[dict]:
    base = {
        EV_IDENTITY: {
            "evidence_type": "delegation",
            "authoritative_source_type": "identity_provider",
            "subject_binding": "actor",
            "freshness_requirement": LONG_FRESH,
            "validation_method": "signature_verification",
            "allowed_issuers": ["idp.example"],
        },
        EV_ALLOWANCE: {
            "evidence_type": "allowance",
            "authoritative_source_type": "account_state",
            "subject_binding": "actor",
            "freshness_requirement": "P1D",
            "allowed_issuers": ["ledger.example"],
        },
        EV_APPROVAL: {
            "evidence_type": "manager_approval",
            "authoritative_source_type": "approval_workflow",
            "subject_binding": "actor",
            "freshness_requirement": LONG_FRESH,
            "allowed_issuers": ["approvals.example"],
        },
        EV_MERCHANT: {
            "evidence_type": "vendor_approval",
            "authoritative_source_type": "external_application",
            "subject_binding": "target",
            "freshness_requirement": LONG_FRESH,
            "allowed_issuers": ["procurement.example"],
        },
        EV_EXECUTION: {
            "evidence_type": "execution_result",
            "authoritative_source_type": "execution_result",
            "subject_binding": "actor",
            "target_binding": "target",
            "freshness_requirement": LONG_FRESH,
            "allowed_issuers": ["execution.example"],
        },
    }
    out = []
    for ev_id, control_id in (
        (EV_IDENTITY, CTL_IDENTITY),
        (EV_ALLOWANCE, CTL_ALLOWANCE),
        (EV_APPROVAL, CTL_APPROVAL),
        (EV_MERCHANT, CTL_MERCHANT),
        (EV_EXECUTION, CTL_EXECUTION),
    ):
        entry = dict(base[ev_id])
        entry["evidence_requirement_id"] = ev_id
        entry["control_ids"] = [control_id]
        entry["minimum_cardinality"] = 1
        entry["mandatory"] = True
        entry.update(evidence_overrides.get(ev_id, {}))
        out.append(entry)
    return out


def _package_payload(control_overrides, evidence_overrides):
    return ExecutableGovernancePackageCreate(
        organization_id=ORG,
        package_name="generic-policy",
        package_version="1.0.0",
        requirements=_requirements(),
        control_definitions=_controls(control_overrides),
        evidence_requirements=_evidence(evidence_overrides),
        decision_conditions=[
            {
                "condition_id": "DC-1",
                "expression": "True",
                "resulting_decision": "APPROVED",
                "priority": 100,
                "reason_code": "OK",
                "terminal": True,
            }
        ],
        metadata={},
    )


def _publish(db, control_overrides, evidence_overrides):
    pkg = governance_package_service.create(
        db, _package_payload(control_overrides, evidence_overrides)
    )
    result = governance_package_service.validate(db, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(
        db, ORG, pkg.id, approver_principal_id="tester", rationale="approved for test"
    )
    return governance_package_service.publish(db, ORG, pkg.id)


def _resolution(db, *, control_overrides=None, evidence_overrides=None):
    _publish(db, control_overrides or {}, evidence_overrides or {})
    actor = actor_identity_service.create(
        db,
        ActorIdentityCreate(
            organization_id=ORG, actor_type=CanonicalActorType.AI_AGENT
        ),
    )
    intent = intent_service.create(
        db,
        IntentCreate(
            organization_id=ORG,
            intent_type=IntentType.WORKFLOW_ACTION,
            action="perform_action",
            actor_id=actor.id,
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
    return resolution, actor, target


def _base_fixtures(actor_id, target_id):
    return {
        "identity": {
            EV_IDENTITY: {
                "issuer": "idp.example",
                "issued_at": ISSUED,
                "expires_at": FAR_FUTURE,
                "signature": "sig-identity",
                "signature_valid": True,
                "subject_id": actor_id,
                "claims": {"delegation": "granted", "scope": "perform_action"},
            }
        },
        "account": {
            EV_ALLOWANCE: {
                "issuer": "ledger.example",
                "issued_at": utc_now(),
                "expires_at": FAR_FUTURE,
                "subject_id": actor_id,
                "claims": {
                    "remaining": {"amount": "1000.00", "currency": "USD"}
                },
            }
        },
        "approval": {
            EV_APPROVAL: {
                "issuer": "approvals.example",
                "issued_at": ISSUED,
                "expires_at": FAR_FUTURE,
                "subject_id": actor_id,
                "claims": {"approved": True},
            }
        },
        "merchant": {
            EV_MERCHANT: {
                "issuer": "procurement.example",
                "issued_at": ISSUED,
                "expires_at": FAR_FUTURE,
                "subject_id": target_id,
                "claims": {"vendor_status": "approved"},
            }
        },
        "execution": {
            EV_EXECUTION: {
                "issuer": "execution.example",
                "issued_at": ISSUED,
                "expires_at": FAR_FUTURE,
                "subject_id": actor_id,
                "target_id": target_id,
                "claims": {"result": "confirmed"},
            }
        },
    }


def _registry(fixtures) -> ConnectorRegistry:
    return ConnectorRegistry(
        [
            simulators.identity_delegation_connector(
                fixtures=fixtures["identity"], is_mock=True
            ),
            simulators.account_allowance_connector(
                fixtures=fixtures["account"], is_mock=True
            ),
            simulators.approval_connector(
                fixtures=fixtures["approval"], is_mock=True
            ),
            simulators.external_application_connector(
                fixtures=fixtures["merchant"], is_mock=True
            ),
            simulators.execution_result_connector(
                fixtures=fixtures["execution"], is_mock=True
            ),
        ]
    )


def _collect(db, resolution, fixtures):
    return evidence_collection_service.start_collection(
        db, ORG, resolution.id, production_mode=False, registry=_registry(fixtures)
    )


def _run_stages(db, resolution):
    sufficiency = evidence_sufficiency_service.evaluate_for_resolution(
        db, ORG, resolution.id
    )
    controls = control_evaluation_service.evaluate_for_resolution(
        db, ORG, resolution.id
    )
    assessment = assessment_service.assess_for_resolution(db, ORG, resolution.id)
    return sufficiency, controls, assessment


def _req_status(sufficiency, req_id):
    for entry in json.loads(sufficiency.requirement_results):
        if entry["evidence_requirement_id"] == req_id:
            return entry["status"]
    return None


def _control_result(controls, control_id):
    for ce in controls:
        if ce.control_id == control_id:
            return ce.result
    return None


# --------------------------------------------------------------------------- #
# Scenario: all controls satisfied
# --------------------------------------------------------------------------- #
def test_all_controls_satisfied(db_session):
    resolution, actor, target = _resolution(db_session)
    _collect(db_session, resolution, _base_fixtures(actor.id, target.external_identifier))

    sufficiency, controls, assessment = _run_stages(db_session, resolution)

    assert (
        sufficiency.overall_result == EvidenceSufficiencyOutcome.SUFFICIENT.value
    )
    assert len(controls) == 5
    assert all(
        ce.result == ControlEvaluationOutcome.SATISFIED.value for ce in controls
    )
    # Every control evaluation records the exact governance package version and
    # references normalized evidence.
    for ce in controls:
        assert ce.package_version == "1.0.0"
        assert json.loads(ce.evidence_references)
    assert assessment.overall_result == AssessmentOutcome.SATISFIED.value
    summary = json.loads(assessment.mandatory_control_summary)
    assert summary["total"] == 5
    assert summary["satisfied"] == 5


# --------------------------------------------------------------------------- #
# Scenario: one mandatory control not satisfied
# --------------------------------------------------------------------------- #
def test_one_mandatory_control_not_satisfied(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    fixtures["approval"][EV_APPROVAL]["expires_at"] = PAST  # expired
    _collect(db_session, resolution, fixtures)

    sufficiency, controls, assessment = _run_stages(db_session, resolution)

    assert (
        _req_status(sufficiency, EV_APPROVAL)
        == EvidenceRequirementSufficiency.INVALID.value
    )
    assert (
        sufficiency.overall_result
        == EvidenceSufficiencyOutcome.INSUFFICIENT.value
    )
    assert (
        _control_result(controls, CTL_APPROVAL)
        == ControlEvaluationOutcome.NOT_SATISFIED.value
    )
    assert (
        _control_result(controls, CTL_IDENTITY)
        == ControlEvaluationOutcome.SATISFIED.value
    )
    assert assessment.overall_result == AssessmentOutcome.NOT_SATISFIED.value


# --------------------------------------------------------------------------- #
# Scenario: optional control failure does not fail the assessment
# --------------------------------------------------------------------------- #
def test_optional_control_failure(db_session):
    resolution, actor, target = _resolution(
        db_session,
        control_overrides={CTL_MERCHANT: {"mandatory": False}},
        evidence_overrides={EV_MERCHANT: {"mandatory": False}},
    )
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    fixtures["merchant"][EV_MERCHANT]["expires_at"] = PAST  # expired
    _collect(db_session, resolution, fixtures)

    sufficiency, controls, assessment = _run_stages(db_session, resolution)

    # The optional evidence is invalid but does not block overall sufficiency.
    assert (
        _req_status(sufficiency, EV_MERCHANT)
        == EvidenceRequirementSufficiency.INVALID.value
    )
    assert (
        sufficiency.overall_result == EvidenceSufficiencyOutcome.SUFFICIENT.value
    )
    # The optional control fails, but the assessment stays SATISFIED.
    assert (
        _control_result(controls, CTL_MERCHANT)
        == ControlEvaluationOutcome.NOT_SATISFIED.value
    )
    assert assessment.overall_result == AssessmentOutcome.SATISFIED.value
    summary = json.loads(assessment.mandatory_control_summary)
    assert summary["total"] == 4
    assert summary["satisfied"] == 4
    assert summary["optional_total"] == 1


# --------------------------------------------------------------------------- #
# Scenario: stale evidence makes a control not evaluable
# --------------------------------------------------------------------------- #
def test_stale_evidence_makes_control_not_evaluable(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    # Allowance has a P1D freshness window; a 2020 issue date is stale.
    fixtures["account"][EV_ALLOWANCE]["issued_at"] = PAST
    fixtures["account"][EV_ALLOWANCE]["expires_at"] = FAR_FUTURE
    _collect(db_session, resolution, fixtures)

    sufficiency, controls, assessment = _run_stages(db_session, resolution)

    assert (
        _req_status(sufficiency, EV_ALLOWANCE)
        == EvidenceRequirementSufficiency.STALE.value
    )
    assert (
        _control_result(controls, CTL_ALLOWANCE)
        == ControlEvaluationOutcome.NOT_EVALUABLE.value
    )
    assert assessment.overall_result == AssessmentOutcome.NOT_EVALUABLE.value


# --------------------------------------------------------------------------- #
# Scenario: manual approval requirement
# --------------------------------------------------------------------------- #
def test_manual_approval_requirement(db_session):
    resolution, actor, target = _resolution(
        db_session,
        evidence_overrides={EV_APPROVAL: {"validation_method": "manual_review"}},
    )
    _collect(db_session, resolution, _base_fixtures(actor.id, target.external_identifier))

    sufficiency, controls, assessment = _run_stages(db_session, resolution)

    assert (
        _req_status(sufficiency, EV_APPROVAL)
        == EvidenceRequirementSufficiency.MANUAL_REVIEW_REQUIRED.value
    )
    assert (
        sufficiency.overall_result
        == EvidenceSufficiencyOutcome.MANUAL_REVIEW_REQUIRED.value
    )
    assert (
        _control_result(controls, CTL_APPROVAL)
        == ControlEvaluationOutcome.MANUAL_REVIEW_REQUIRED.value
    )
    assert (
        assessment.overall_result
        == AssessmentOutcome.MANUAL_REVIEW_REQUIRED.value
    )


# --------------------------------------------------------------------------- #
# Scenario: deterministic replay
# --------------------------------------------------------------------------- #
def test_deterministic_replay(db_session):
    resolution, actor, target = _resolution(db_session)
    _collect(db_session, resolution, _base_fixtures(actor.id, target.external_identifier))

    suff1, controls1, assessment1 = _run_stages(db_session, resolution)
    suff2, controls2, assessment2 = _run_stages(db_session, resolution)

    # Sufficiency is reproducible for identical inputs.
    assert suff1.result_hash == suff2.result_hash
    # Each control produces the same immutable id + result hash on replay.
    by_id1 = {ce.control_evaluation_id: ce.result_hash for ce in controls1}
    by_id2 = {ce.control_evaluation_id: ce.result_hash for ce in controls2}
    assert by_id1 == by_id2
    # The assessment hash is stable.
    assert assessment1.assessment_hash == assessment2.assessment_hash


# --------------------------------------------------------------------------- #
# Scenario: assessment is separate from decision
# --------------------------------------------------------------------------- #
def test_assessment_is_separate_from_decision(db_session):
    resolution, actor, target = _resolution(db_session)
    _collect(db_session, resolution, _base_fixtures(actor.id, target.external_identifier))

    _, _, assessment = _run_stages(db_session, resolution)

    decision_outcomes = {o.value for o in DecisionOutcome}
    assessment_outcomes = {o.value for o in AssessmentOutcome}
    # The assessment result uses the factual vocabulary, never a business
    # decision (APPROVED / DENIED / ESCALATED).
    assert assessment.overall_result in assessment_outcomes
    assert assessment.overall_result not in decision_outcomes
    # The assessment carries the evidence-sufficiency result but emits no
    # decision fields.
    assert assessment.evidence_sufficiency_result is not None
    assert not hasattr(assessment, "outcome")


# --------------------------------------------------------------------------- #
# Scenario: raw intent assertions cannot satisfy controls without evidence
# --------------------------------------------------------------------------- #
def test_control_not_satisfied_without_normalized_evidence(db_session):
    # The control's expression is a trivially-true assertion, but the evidence
    # connector fails to produce the evidence — the control must not be
    # satisfied without normalized validated evidence.
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    fixtures["merchant"][EV_MERCHANT] = {"behavior": "error", "error": "boom"}
    _collect(db_session, resolution, fixtures)

    sufficiency, controls, assessment = _run_stages(db_session, resolution)

    # No valid normalized evidence could be produced for the requirement.
    assert _req_status(sufficiency, EV_MERCHANT) in (
        EvidenceRequirementSufficiency.MISSING.value,
        EvidenceRequirementSufficiency.NOT_EVALUABLE.value,
    )
    # Expression is "True" yet the control is NOT satisfied — the raw assertion
    # cannot stand in for normalized evidence.
    merchant_result = _control_result(controls, CTL_MERCHANT)
    assert merchant_result != ControlEvaluationOutcome.SATISFIED.value
    assert merchant_result in (
        ControlEvaluationOutcome.NOT_SATISFIED.value,
        ControlEvaluationOutcome.NOT_EVALUABLE.value,
    )
    # And the control that references evidence-only facts is never satisfied by
    # a raw assertion: the overall assessment is not SATISFIED.
    assert assessment.overall_result != AssessmentOutcome.SATISFIED.value


# --------------------------------------------------------------------------- #
# Scenario: control expression is evaluated against normalized evidence only
# --------------------------------------------------------------------------- #
def test_control_expression_evaluates_normalized_evidence(db_session):
    resolution, actor, target = _resolution(
        db_session,
        control_overrides={
            # Matches the normalized merchant claim -> SATISFIED.
            CTL_MERCHANT: {
                "evaluation_expression": (
                    "evidence['EV-MERCHANT']['claims']['vendor_status']"
                    " == 'approved'"
                )
            },
            # Does not match the normalized execution claim -> NOT_SATISFIED.
            CTL_EXECUTION: {
                "evaluation_expression": (
                    "evidence['EV-EXECUTION']['claims']['result'] == 'rejected'"
                )
            },
        },
    )
    _collect(db_session, resolution, _base_fixtures(actor.id, target.external_identifier))

    _, controls, assessment = _run_stages(db_session, resolution)

    assert (
        _control_result(controls, CTL_MERCHANT)
        == ControlEvaluationOutcome.SATISFIED.value
    )
    assert (
        _control_result(controls, CTL_EXECUTION)
        == ControlEvaluationOutcome.NOT_SATISFIED.value
    )
    # The observed value is recorded on the immutable result.
    merchant = next(c for c in controls if c.control_id == CTL_MERCHANT)
    assert json.loads(merchant.observed_value) is True
    assert assessment.overall_result == AssessmentOutcome.NOT_SATISFIED.value
