"""Tests for the Control Determination and Evidence Requirement Resolution
runtime stages.

These stages run after Applicability Evaluation and before evidence collection.
They are deterministic and are the sole authority for which controls apply — the
decision engine never decides control applicability. The tests cover the
required scenarios:

* approved-airline control selected,
* spend-limit control selected,
* manager-approval evidence required only when the threshold condition applies,
* international authorization required only for international travel,
* shared identity evidence deduplicated,
* missing applicability basis produces UNRESOLVED evidence requirements rather
  than silent success.
"""

from __future__ import annotations

import pytest

from app.schemas.canonical.actor_identity import ActorIdentityCreate
from app.schemas.canonical.control_evidence import (
    ControlDeterminationCreate,
    EvidenceRequirementResolutionCreate,
)
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
    control_determination_service,
    evidence_requirement_service,
    governance_package_service,
    intent_service,
    operational_context_service,
    policy_resolution_service,
    target_service,
)
from app.utils.canonical_enums import (
    CanonicalActorType,
    ControlDeterminationStatus,
    IntentType,
    RequiredEvidenceState,
    TargetType,
)

ORG = "org-travel"

# Manager approval is required above this spend threshold (integer minor units).
SPEND_THRESHOLD = 100_000


# --------------------------------------------------------------------------- #
# Package builder
# --------------------------------------------------------------------------- #
def _requirements() -> list[dict]:
    return [
        {
            "requirement_id": "REQ-APPROVED-AIRLINE",
            "source_reference": "TRAVEL §1",
            "normalized_text": "Bookings must use an approved airline.",
            "requirement_type": "vendor_restriction",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-APPROVED-AIRLINE"],
            "applicability_criteria": {
                "op": "equals",
                "field": "target.classification",
                "value": "AIRLINE",
            },
        },
        {
            "requirement_id": "REQ-SPEND-LIMIT",
            "source_reference": "TRAVEL §2",
            "normalized_text": "Spend must remain within the configured limit.",
            "requirement_type": "spend_limit",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-SPEND-LIMIT"],
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.action",
                "value": "book_travel",
            },
        },
        {
            "requirement_id": "REQ-MANAGER-APPROVAL",
            "source_reference": "TRAVEL §3",
            "normalized_text": (
                "Manager approval is required above the spend threshold."
            ),
            "requirement_type": "approval",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-MANAGER-APPROVAL"],
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.action",
                "value": "book_travel",
            },
            # The obligation applies when booking travel; the *condition* that
            # actually triggers it is the spend exceeding the threshold. When
            # unmet the requirement is CONDITIONAL (evidence conditionally
            # required); when met it is APPLICABLE (evidence required).
            "condition_criteria": {
                "op": "greater_than",
                "field": "intent.amount_minor",
                "value": SPEND_THRESHOLD,
            },
        },
        {
            "requirement_id": "REQ-INTL-AUTH",
            "source_reference": "TRAVEL §4",
            "normalized_text": "International travel requires authorization.",
            "requirement_type": "authorization",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-INTL-AUTH"],
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.parameters.is_international",
                "value": True,
            },
        },
        {
            "requirement_id": "REQ-JURISDICTION",
            "source_reference": "TRAVEL §5",
            "normalized_text": "Travel is restricted to approved jurisdictions.",
            "requirement_type": "location_restriction",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-JURISDICTION"],
            "applicability_criteria": {
                "op": "equals",
                "field": "context.jurisdiction",
                "value": "US",
            },
        },
    ]


def _controls() -> list[dict]:
    return [
        {
            "control_id": "CTL-APPROVED-AIRLINE",
            "requirement_ids": ["REQ-APPROVED-AIRLINE"],
            "control_objective": "Only approved airlines may be booked.",
            "evaluation_expression": "target.classification == 'AIRLINE'",
            "expected_outcome": "APPROVED",
            "mandatory": True,
            "severity": "HIGH",
            "failure_disposition": "DENY",
            # Shares the identity evidence with the spend-limit control.
            "evidence_requirement_ids": ["EV-IDENTITY", "EV-AIRLINE-APPROVAL"],
        },
        {
            "control_id": "CTL-SPEND-LIMIT",
            "requirement_ids": ["REQ-SPEND-LIMIT"],
            "control_objective": "Spend must remain within the limit.",
            "evaluation_expression": "intent.amount_minor <= limit",
            "expected_outcome": "APPROVED",
            "mandatory": True,
            "severity": "MEDIUM",
            "failure_disposition": "ESCALATE",
            # Shares the identity evidence with the approved-airline control.
            "evidence_requirement_ids": ["EV-IDENTITY"],
        },
        {
            "control_id": "CTL-MANAGER-APPROVAL",
            "requirement_ids": ["REQ-MANAGER-APPROVAL"],
            "control_objective": "Manager approval above the threshold.",
            "evaluation_expression": "evidence.manager_approval == true",
            "expected_outcome": "APPROVED",
            "mandatory": True,
            "severity": "HIGH",
            "failure_disposition": "ESCALATE",
            "evidence_requirement_ids": ["EV-MANAGER-APPROVAL"],
        },
        {
            "control_id": "CTL-INTL-AUTH",
            "requirement_ids": ["REQ-INTL-AUTH"],
            "control_objective": "International travel authorization.",
            "evaluation_expression": "evidence.intl_auth == true",
            "expected_outcome": "APPROVED",
            "mandatory": True,
            "severity": "CRITICAL",
            "failure_disposition": "DENY",
            "evidence_requirement_ids": ["EV-INTL-AUTH"],
        },
        {
            "control_id": "CTL-JURISDICTION",
            "requirement_ids": ["REQ-JURISDICTION"],
            "control_objective": "Jurisdiction restriction.",
            "evaluation_expression": "context.jurisdiction == 'US'",
            "expected_outcome": "APPROVED",
            "mandatory": True,
            "severity": "MEDIUM",
            "failure_disposition": "DENY",
            "evidence_requirement_ids": [],
        },
    ]


def _evidence() -> list[dict]:
    return [
        {
            "evidence_requirement_id": "EV-IDENTITY",
            "control_ids": ["CTL-APPROVED-AIRLINE", "CTL-SPEND-LIMIT"],
            "evidence_type": "verified_identity",
            "authoritative_source_type": "identity_provider",
            "subject_binding": "actor",
            "target_binding": None,
            "freshness_requirement": "P30D",
            "validation_method": "signature_verification",
            "minimum_cardinality": 1,
            "mandatory": True,
            "allowed_issuers": ["idp.example"],
        },
        {
            "evidence_requirement_id": "EV-AIRLINE-APPROVAL",
            "control_ids": ["CTL-APPROVED-AIRLINE"],
            "evidence_type": "vendor_approval",
            "authoritative_source_type": "procurement_system",
            "subject_binding": "target",
            "minimum_cardinality": 1,
            "mandatory": True,
        },
        {
            "evidence_requirement_id": "EV-MANAGER-APPROVAL",
            "control_ids": ["CTL-MANAGER-APPROVAL"],
            "evidence_type": "manager_approval",
            "authoritative_source_type": "approval_workflow",
            "subject_binding": "actor",
            "freshness_requirement": "P7D",
            "validation_method": "workflow_attestation",
            "minimum_cardinality": 1,
            "mandatory": True,
        },
        {
            "evidence_requirement_id": "EV-INTL-AUTH",
            "control_ids": ["CTL-INTL-AUTH"],
            "evidence_type": "international_authorization",
            "authoritative_source_type": "compliance_officer",
            "subject_binding": "actor",
            "minimum_cardinality": 1,
            "mandatory": True,
        },
    ]


def _create_payload() -> ExecutableGovernancePackageCreate:
    return ExecutableGovernancePackageCreate(
        organization_id=ORG,
        package_name="travel-policy",
        package_version="1.0.0",
        requirements=_requirements(),
        control_definitions=_controls(),
        evidence_requirements=_evidence(),
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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _publish(db):
    pkg = governance_package_service.create(db, _create_payload())
    result = governance_package_service.validate(db, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(
        db, ORG, pkg.id, approver_principal_id="tester", rationale="approved for test"
    )
    return governance_package_service.publish(db, ORG, pkg.id)


def _actor(db):
    return actor_identity_service.create(
        db,
        ActorIdentityCreate(
            organization_id=ORG, actor_type=CanonicalActorType.HUMAN
        ),
    )


def _intent(db, actor_id, *, is_international=False, amount_minor=50_000):
    return intent_service.create(
        db,
        IntentCreate(
            organization_id=ORG,
            intent_type=IntentType.WORKFLOW_ACTION,
            action="book_travel",
            actor_id=actor_id,
            amount_minor=amount_minor,
            amount_currency="USD",
            parameters={"is_international": is_international},
        ),
    )


def _target(db):
    return target_service.create(
        db,
        TargetCreate(
            organization_id=ORG,
            target_type=TargetType.MERCHANT,
            external_identifier="airline-01",
            classification="AIRLINE",
        ),
    )


def _context(db, jurisdiction="US"):
    return operational_context_service.create(
        db,
        OperationalContextCreate(
            organization_id=ORG,
            jurisdiction=jurisdiction,
            environment="PRODUCTION",
        ),
    )


def _resolve(db, actor, intent, target=None, context=None):
    return policy_resolution_service.resolve(
        db,
        PolicyResolutionCreate(
            organization_id=ORG,
            actor_identity_id=actor.id,
            intent_id=intent.id,
            target_id=target.id if target else None,
            operational_context_id=context.id if context else None,
        ),
    )


def _run_applicability(db, resolution):
    return applicability_service.evaluate_for_resolution(
        db,
        ApplicabilityEvaluationCreate(
            organization_id=ORG, policy_resolution_id=resolution.id
        ),
    )


def _determine_controls(db, resolution):
    return control_determination_service.determine_for_resolution(
        db,
        ControlDeterminationCreate(
            organization_id=ORG, policy_resolution_id=resolution.id
        ),
    )


def _resolve_evidence(db, resolution):
    return evidence_requirement_service.resolve_for_resolution(
        db,
        EvidenceRequirementResolutionCreate(
            organization_id=ORG, policy_resolution_id=resolution.id
        ),
    )


def _controls_by_id(control_set) -> dict[str, dict]:
    import json

    return {c["control_id"]: c for c in json.loads(control_set.controls)}


def _evidence_by_id(evidence_set) -> dict[str, dict]:
    import json

    return {
        e["evidence_requirement_id"]: e
        for e in json.loads(evidence_set.evidence_requirements)
    }


@pytest.fixture()
def domestic(db_session):
    """A fully-resolved domestic booking below the manager-approval threshold."""
    _publish(db_session)
    actor = _actor(db_session)
    intent = _intent(
        db_session, actor.id, is_international=False, amount_minor=50_000
    )
    resolution = _resolve(
        db_session, actor, intent, _target(db_session), _context(db_session)
    )
    _run_applicability(db_session, resolution)
    return db_session, resolution


# --------------------------------------------------------------------------- #
# Control Determination
# --------------------------------------------------------------------------- #
def test_approved_airline_control_selected(domestic):
    db, resolution = domestic
    controls = _controls_by_id(_determine_controls(db, resolution))

    assert "CTL-APPROVED-AIRLINE" in controls
    ctrl = controls["CTL-APPROVED-AIRLINE"]
    assert ctrl["status"] == ControlDeterminationStatus.APPLICABLE.value
    # Traceable to its requirement and governance package version.
    assert ctrl["requirement_ids"] == ["REQ-APPROVED-AIRLINE"]
    assert ctrl["governance_packages"][0]["package_version"] == "1.0.0"
    assert ctrl["applicable_control_id"]
    assert ctrl["determination_hash"]
    assert ctrl["mandatory"] is True
    assert ctrl["severity"] == "HIGH"
    assert ctrl["failure_disposition"] == "DENY"
    assert ctrl["expected_outcome"] == "APPROVED"


def test_spend_limit_control_selected(domestic):
    db, resolution = domestic
    controls = _controls_by_id(_determine_controls(db, resolution))

    assert "CTL-SPEND-LIMIT" in controls
    assert (
        controls["CTL-SPEND-LIMIT"]["status"]
        == ControlDeterminationStatus.APPLICABLE.value
    )


def test_not_applicable_controls_excluded(domestic):
    db, resolution = domestic
    controls = _controls_by_id(_determine_controls(db, resolution))

    # Domestic booking → international authorization requirement NOT_APPLICABLE.
    assert "CTL-INTL-AUTH" not in controls


def test_conditional_status_preserved_below_threshold(domestic):
    db, resolution = domestic
    controls = _controls_by_id(_determine_controls(db, resolution))

    # Below the threshold the manager-approval requirement is CONDITIONAL and
    # the control preserves that status rather than collapsing it.
    assert (
        controls["CTL-MANAGER-APPROVAL"]["status"]
        == ControlDeterminationStatus.CONDITIONAL.value
    )


def test_manager_approval_applicable_above_threshold(db_session):
    _publish(db_session)
    actor = _actor(db_session)
    intent = _intent(
        db_session, actor.id, is_international=False, amount_minor=250_000
    )
    resolution = _resolve(
        db_session, actor, intent, _target(db_session), _context(db_session)
    )
    _run_applicability(db_session, resolution)
    controls = _controls_by_id(_determine_controls(db_session, resolution))

    assert (
        controls["CTL-MANAGER-APPROVAL"]["status"]
        == ControlDeterminationStatus.APPLICABLE.value
    )


def test_international_authorization_control_only_for_international(db_session):
    _publish(db_session)
    actor = _actor(db_session)
    intent = _intent(db_session, actor.id, is_international=True)
    resolution = _resolve(
        db_session, actor, intent, _target(db_session), _context(db_session)
    )
    _run_applicability(db_session, resolution)
    controls = _controls_by_id(_determine_controls(db_session, resolution))

    assert "CTL-INTL-AUTH" in controls
    assert (
        controls["CTL-INTL-AUTH"]["status"]
        == ControlDeterminationStatus.APPLICABLE.value
    )


def test_control_determination_deterministic_replay(domestic):
    db, resolution = domestic
    set_a = _determine_controls(db, resolution)
    set_b = _determine_controls(db, resolution)
    assert set_a.id != set_b.id
    assert set_a.input_hash == set_b.input_hash
    assert set_a.result_hash == set_b.result_hash


# --------------------------------------------------------------------------- #
# Evidence Requirement Resolution
# --------------------------------------------------------------------------- #
def test_shared_identity_evidence_deduplicated(domestic):
    db, resolution = domestic
    _determine_controls(db, resolution)
    evidence = _evidence_by_id(_resolve_evidence(db, resolution))

    identity = evidence["EV-IDENTITY"]
    # A single deduplicated entry mapping to both controls that require it.
    assert identity["control_ids"] == ["CTL-APPROVED-AIRLINE", "CTL-SPEND-LIMIT"]
    assert identity["state"] == RequiredEvidenceState.REQUIRED.value
    # Traceable to one or more controls and their requirements.
    assert len(identity["applicable_control_ids"]) == 2
    assert set(identity["requirement_ids"]) == {
        "REQ-APPROVED-AIRLINE",
        "REQ-SPEND-LIMIT",
    }
    # Defined evidence attributes are carried through.
    assert identity["evidence_type"] == "verified_identity"
    assert identity["allowed_source_type"] == "identity_provider"
    assert identity["subject"] == "actor"
    assert identity["freshness_threshold"] == "P30D"
    assert identity["validation_method"] == "signature_verification"
    assert identity["cardinality"] == 1
    assert identity["mandatory"] is True
    assert identity["allowed_issuers"] == ["idp.example"]


def test_manager_approval_evidence_conditional_below_threshold(domestic):
    db, resolution = domestic
    evidence = _evidence_by_id(_resolve_evidence(db, resolution))

    # Below the threshold the manager-approval evidence is required only when
    # the threshold condition applies → CONDITIONAL, not silently REQUIRED.
    assert (
        evidence["EV-MANAGER-APPROVAL"]["state"]
        == RequiredEvidenceState.CONDITIONAL.value
    )


def test_manager_approval_evidence_required_above_threshold(db_session):
    _publish(db_session)
    actor = _actor(db_session)
    intent = _intent(
        db_session, actor.id, is_international=False, amount_minor=250_000
    )
    resolution = _resolve(
        db_session, actor, intent, _target(db_session), _context(db_session)
    )
    _run_applicability(db_session, resolution)
    evidence = _evidence_by_id(_resolve_evidence(db_session, resolution))

    assert (
        evidence["EV-MANAGER-APPROVAL"]["state"]
        == RequiredEvidenceState.REQUIRED.value
    )


def test_international_authorization_evidence_only_for_international(db_session):
    _publish(db_session)
    actor = _actor(db_session)

    # Domestic → international authorization evidence NOT_REQUIRED.
    dom_intent = _intent(db_session, actor.id, is_international=False)
    dom_res = _resolve(
        db_session, actor, dom_intent, _target(db_session), _context(db_session)
    )
    _run_applicability(db_session, dom_res)
    dom_evidence = _evidence_by_id(_resolve_evidence(db_session, dom_res))
    assert (
        dom_evidence["EV-INTL-AUTH"]["state"]
        == RequiredEvidenceState.NOT_REQUIRED.value
    )

    # International → international authorization evidence REQUIRED.
    intl_intent = _intent(db_session, actor.id, is_international=True)
    intl_res = _resolve(
        db_session, actor, intl_intent, _target(db_session), _context(db_session)
    )
    _run_applicability(db_session, intl_res)
    intl_evidence = _evidence_by_id(_resolve_evidence(db_session, intl_res))
    assert (
        intl_evidence["EV-INTL-AUTH"]["state"]
        == RequiredEvidenceState.REQUIRED.value
    )
    assert intl_evidence["EV-INTL-AUTH"]["control_ids"] == ["CTL-INTL-AUTH"]


def test_missing_applicability_basis_produces_unresolved_evidence(db_session):
    _publish(db_session)
    actor = _actor(db_session)
    intent = _intent(db_session, actor.id, is_international=False)
    # Resolve WITHOUT running applicability evaluation → no applicability basis.
    resolution = _resolve(
        db_session, actor, intent, _target(db_session), _context(db_session)
    )

    control_set = _determine_controls(db_session, resolution)
    controls = _controls_by_id(control_set)
    # Controls surface as INDETERMINATE, never silently NOT_APPLICABLE.
    assert controls  # controls are still present
    assert all(
        c["status"] == ControlDeterminationStatus.INDETERMINATE.value
        for c in controls.values()
    )

    evidence = _evidence_by_id(_resolve_evidence(db_session, resolution))
    # Missing basis → UNRESOLVED evidence rather than silent success.
    assert evidence["EV-IDENTITY"]["state"] == RequiredEvidenceState.UNRESOLVED.value
    assert all(
        e["state"] == RequiredEvidenceState.UNRESOLVED.value
        for e in evidence.values()
    )


def test_evidence_resolution_computes_control_set_on_demand(db_session):
    """Evidence resolution triggers Control Determination if not yet run."""
    _publish(db_session)
    actor = _actor(db_session)
    intent = _intent(db_session, actor.id)
    resolution = _resolve(
        db_session, actor, intent, _target(db_session), _context(db_session)
    )
    _run_applicability(db_session, resolution)

    # No control determination run yet; evidence resolution must materialise it.
    evidence_set = _resolve_evidence(db_session, resolution)
    assert evidence_set.applicable_control_set_id
    control_set = control_determination_service.get(
        db_session, ORG, evidence_set.applicable_control_set_id
    )
    assert control_set is not None


def test_every_required_evidence_item_is_traceable_to_controls(domestic):
    db, resolution = domestic
    evidence = _evidence_by_id(_resolve_evidence(db, resolution))
    for entry in evidence.values():
        if entry["state"] in (
            RequiredEvidenceState.REQUIRED.value,
            RequiredEvidenceState.OPTIONAL.value,
            RequiredEvidenceState.CONDITIONAL.value,
        ):
            assert entry["control_ids"], entry
            assert entry["resolution_hash"]
