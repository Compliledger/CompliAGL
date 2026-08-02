"""Tests for the Policy Resolution and Applicability Evaluation runtime stages.

These stages are deterministic and separate from the decision engine. The tests
cover the required scenarios:

* domestic travel requirement applicable,
* international requirement not applicable to domestic travel,
* international prior authorization applicable to international travel,
* expired policy excluded,
* superseded package excluded,
* conflicting packages,
* missing context producing INDETERMINATE,
* deterministic replay producing identical results and hashes.
"""

from __future__ import annotations

import json
from datetime import timedelta

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
    governance_package_service,
    intent_service,
    operational_context_service,
    policy_resolution_service,
    target_service,
)
from app.utils.canonical_enums import (
    ApplicabilityResult,
    CanonicalActorType,
    IntentType,
    PolicyResolutionStatus,
    TargetType,
)
from app.utils.timestamps import utc_now

ORG = "org-travel"


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def _requirements() -> list[dict]:
    """Requirements carrying structured deterministic applicability criteria."""
    return [
        {
            "requirement_id": "REQ-DOMESTIC",
            "source_reference": "TRAVEL §1",
            "normalized_text": "Domestic economy travel is permitted.",
            "requirement_type": "travel_booking",
            "classification": "PERMISSION",
            "mapped_control_ids": ["CTL-1"],
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.parameters.is_international",
                "value": False,
            },
        },
        {
            "requirement_id": "REQ-INTERNATIONAL",
            "source_reference": "TRAVEL §2",
            "normalized_text": "International travel is governed separately.",
            "requirement_type": "travel_booking",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-1"],
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.parameters.is_international",
                "value": True,
            },
        },
        {
            "requirement_id": "REQ-INTL-PRIORAUTH",
            "source_reference": "TRAVEL §3",
            "normalized_text": "International travel requires prior authorization.",
            "requirement_type": "authorization",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-1"],
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.parameters.is_international",
                "value": True,
            },
            "condition_criteria": {
                "op": "equals",
                "field": "intent.parameters.prior_authorization",
                "value": True,
            },
        },
        {
            "requirement_id": "REQ-JURISDICTION",
            "source_reference": "TRAVEL §4",
            "normalized_text": "Travel is restricted to approved jurisdictions.",
            "requirement_type": "location_restriction",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-1"],
            "applicability_criteria": {
                "op": "equals",
                "field": "context.jurisdiction",
                "value": "US",
            },
        },
    ]


def _create_payload(
    *,
    name: str = "travel-policy",
    version: str = "1.0.0",
    requirements=None,
    metadata=None,
    effective_at=None,
    expires_at=None,
    supersedes_package_id=None,
) -> ExecutableGovernancePackageCreate:
    return ExecutableGovernancePackageCreate(
        organization_id=ORG,
        package_name=name,
        package_version=version,
        effective_at=effective_at,
        expires_at=expires_at,
        supersedes_package_id=supersedes_package_id,
        requirements=requirements if requirements is not None else _requirements(),
        control_definitions=[
            {
                "control_id": "CTL-1",
                "requirement_ids": [
                    r["requirement_id"]
                    for r in (requirements if requirements is not None else _requirements())
                ],
                "control_objective": "Bind requirements to a control.",
                "evaluation_expression": "True",
            }
        ],
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
        metadata=metadata or {},
    )


def _publish(db, payload: ExecutableGovernancePackageCreate):
    pkg = governance_package_service.create(db, payload)
    result = governance_package_service.validate(db, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(db, ORG, pkg.id, approved_by="tester")
    return governance_package_service.publish(db, ORG, pkg.id)


def _actor(db):
    return actor_identity_service.create(
        db,
        ActorIdentityCreate(
            organization_id=ORG, actor_type=CanonicalActorType.HUMAN
        ),
    )


def _intent(db, actor_id, *, is_international=False, prior_authorization=False):
    return intent_service.create(
        db,
        IntentCreate(
            organization_id=ORG,
            intent_type=IntentType.WORKFLOW_ACTION,
            action="book_travel",
            actor_id=actor_id,
            parameters={
                "is_international": is_international,
                "prior_authorization": prior_authorization,
            },
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


def _applicability(db, resolution):
    return applicability_service.evaluate_for_resolution(
        db,
        ApplicabilityEvaluationCreate(
            organization_id=ORG, policy_resolution_id=resolution.id
        ),
    )


def _by_requirement(records) -> dict[str, str]:
    return {r.requirement_id: r.result for r in records}


# --------------------------------------------------------------------------- #
# Scenario tests
# --------------------------------------------------------------------------- #
def test_domestic_travel_requirement_applicable(db_session):
    _publish(db_session, _create_payload())
    actor = _actor(db_session)
    intent = _intent(db_session, actor.id, is_international=False)
    context = _context(db_session)

    resolution = _resolve(db_session, actor, intent, _target(db_session), context)
    assert resolution.status == PolicyResolutionStatus.RESOLVED.value

    results = _by_requirement(_applicability(db_session, resolution))
    assert results["REQ-DOMESTIC"] == ApplicabilityResult.APPLICABLE.value


def test_international_requirement_not_applicable_to_domestic(db_session):
    _publish(db_session, _create_payload())
    actor = _actor(db_session)
    intent = _intent(db_session, actor.id, is_international=False)
    context = _context(db_session)

    resolution = _resolve(db_session, actor, intent, _target(db_session), context)
    results = _by_requirement(_applicability(db_session, resolution))

    assert results["REQ-INTERNATIONAL"] == ApplicabilityResult.NOT_APPLICABLE.value
    assert results["REQ-INTL-PRIORAUTH"] == ApplicabilityResult.NOT_APPLICABLE.value


def test_international_prior_authorization_applicable(db_session):
    _publish(db_session, _create_payload())
    actor = _actor(db_session)
    intent = _intent(
        db_session, actor.id, is_international=True, prior_authorization=True
    )
    context = _context(db_session)

    resolution = _resolve(db_session, actor, intent, _target(db_session), context)
    results = _by_requirement(_applicability(db_session, resolution))

    assert results["REQ-INTERNATIONAL"] == ApplicabilityResult.APPLICABLE.value
    assert results["REQ-INTL-PRIORAUTH"] == ApplicabilityResult.APPLICABLE.value
    assert results["REQ-DOMESTIC"] == ApplicabilityResult.NOT_APPLICABLE.value


def test_international_without_prior_authorization_is_conditional(db_session):
    _publish(db_session, _create_payload())
    actor = _actor(db_session)
    intent = _intent(
        db_session, actor.id, is_international=True, prior_authorization=False
    )
    context = _context(db_session)

    resolution = _resolve(db_session, actor, intent, _target(db_session), context)
    results = _by_requirement(_applicability(db_session, resolution))

    assert results["REQ-INTL-PRIORAUTH"] == ApplicabilityResult.CONDITIONAL.value


def test_expired_policy_excluded(db_session):
    now = utc_now()
    _publish(
        db_session,
        _create_payload(
            name="active-policy",
            effective_at=now - timedelta(days=10),
        ),
    )
    expired = _publish(
        db_session,
        _create_payload(
            name="expired-policy",
            effective_at=now - timedelta(days=30),
            expires_at=now - timedelta(days=1),
        ),
    )

    actor = _actor(db_session)
    intent = _intent(db_session, actor.id)
    resolution = _resolve(db_session, actor, intent, context=_context(db_session))

    assert expired.id not in json.loads(resolution.candidate_package_ids)
    selected_ids = {p["package_id"] for p in json.loads(resolution.selected_packages)}
    assert expired.id not in selected_ids


def test_superseded_package_excluded(db_session):
    v1 = _publish(db_session, _create_payload(name="versioned", version="1.0.0"))
    v2 = _publish(
        db_session,
        _create_payload(
            name="versioned", version="2.0.0", supersedes_package_id=v1.id
        ),
    )

    actor = _actor(db_session)
    intent = _intent(db_session, actor.id)
    resolution = _resolve(db_session, actor, intent, context=_context(db_session))

    candidates = json.loads(resolution.candidate_package_ids)
    assert v1.id not in candidates
    assert v2.id in candidates


def test_conflicting_packages_detected_and_resolved(db_session):
    # Two published packages governing the same policy domain → conflict.
    low_priority = _publish(
        db_session,
        _create_payload(
            name="travel-strict",
            metadata={"policy_domain": "travel", "priority": 10},
        ),
    )
    _publish(
        db_session,
        _create_payload(
            name="travel-relaxed",
            metadata={"policy_domain": "travel", "priority": 50},
        ),
    )

    actor = _actor(db_session)
    intent = _intent(db_session, actor.id)
    resolution = _resolve(db_session, actor, intent, context=_context(db_session))

    assert resolution.status == PolicyResolutionStatus.CONFLICT_RESOLVED.value
    conflicts = json.loads(resolution.conflicts)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict["policy_domain"] == "travel"
    # Lower priority number wins.
    assert conflict["winner_package_id"] == low_priority.id
    selected_ids = {p["package_id"] for p in json.loads(resolution.selected_packages)}
    assert selected_ids == {low_priority.id}


def test_missing_context_produces_indeterminate(db_session):
    _publish(db_session, _create_payload())
    actor = _actor(db_session)
    intent = _intent(db_session, actor.id, is_international=False)

    # No operational context supplied.
    resolution = _resolve(db_session, actor, intent, _target(db_session), None)
    results = _by_requirement(_applicability(db_session, resolution))

    # The jurisdiction requirement references missing context → INDETERMINATE,
    # never silently NOT_APPLICABLE.
    assert results["REQ-JURISDICTION"] == ApplicabilityResult.INDETERMINATE.value
    # A requirement that does not depend on context still resolves normally.
    assert results["REQ-DOMESTIC"] == ApplicabilityResult.APPLICABLE.value


def test_indeterminate_is_never_silently_not_applicable(db_session):
    _publish(db_session, _create_payload())
    actor = _actor(db_session)
    intent = _intent(db_session, actor.id)
    resolution = _resolve(db_session, actor, intent, None, None)
    records = _applicability(db_session, resolution)
    jurisdiction = next(r for r in records if r.requirement_id == "REQ-JURISDICTION")
    assert jurisdiction.result == ApplicabilityResult.INDETERMINATE.value
    assert jurisdiction.result != ApplicabilityResult.NOT_APPLICABLE.value


def test_deterministic_replay_identical_hashes(db_session):
    _publish(db_session, _create_payload())
    actor = _actor(db_session)
    intent = _intent(
        db_session, actor.id, is_international=True, prior_authorization=True
    )
    context = _context(db_session)
    target = _target(db_session)

    res_a = _resolve(db_session, actor, intent, target, context)
    res_b = _resolve(db_session, actor, intent, target, context)

    # Different record identities, identical deterministic hashes.
    assert res_a.id != res_b.id
    assert res_a.input_hash == res_b.input_hash
    assert res_a.result_hash == res_b.result_hash

    app_a = {r.requirement_id: r for r in _applicability(db_session, res_a)}
    app_b = {r.requirement_id: r for r in _applicability(db_session, res_b)}
    assert set(app_a) == set(app_b)
    for rid, record_a in app_a.items():
        record_b = app_b[rid]
        assert record_a.result == record_b.result
        assert record_a.input_hash == record_b.input_hash
        assert record_a.result_hash == record_b.result_hash


def test_persisted_records_capture_required_fields(db_session):
    _publish(db_session, _create_payload())
    actor = _actor(db_session)
    intent = _intent(db_session, actor.id, is_international=False)
    context = _context(db_session)
    resolution = _resolve(db_session, actor, intent, _target(db_session), context)
    records = _applicability(db_session, resolution)

    record = records[0]
    # Every field required by the acceptance criteria is present.
    assert record.id  # evaluation ID
    assert record.requirement_id
    assert record.package_id and record.package_version
    assert record.actor_identity_id == actor.id
    assert record.intent_id == intent.id
    assert record.operational_context_id == context.id
    assert record.result
    assert record.evaluated_expression is not None
    assert record.observed_values is not None
    assert record.reason_codes is not None
    assert record.engine_version
    assert record.evaluated_at is not None
    assert record.input_hash and record.result_hash
