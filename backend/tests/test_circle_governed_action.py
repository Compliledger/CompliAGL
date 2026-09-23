"""``governed_action_service.propose`` through the Circle treasury package.

Covers the 5 scenarios required by the PR 3a prompt plus two more exercising
the remaining decision-condition priorities (20, 30), and one API-level test
through the thin ``POST /api/v1/governed-actions`` route.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.db import seed
from app.db.circle_treasury_package import build_circle_treasury_package
from app.models.actor_identity import ActorIdentity
from app.services.canonical import authorization_service, governance_package_service
from app.services.canonical import governed_action_service
from app.services.canonical.errors import ConflictError
from app.services.evidence.connectors import ConnectorRegistry
from app.services.evidence.connectors.compliledger_assurance import (
    CIRCLE_CONTROL_ID,
    CompliLedgerAssuranceConnector,
)
from app.utils.canonical_enums import DecisionOutcome, IntentType

ORG = "circle-mvp-demo"
RECIPIENT = "0xRECIPIENT"
FIVE_USDC_MINOR = 5_000_000
TWENTY_FIVE_USDC_MINOR = 25_000_000


@pytest.fixture()
def published_package(db_session):
    seed.seed_organizations(db_session)
    seed.seed_circle_treasury_agent(db_session)
    payload = build_circle_treasury_package(ORG)
    pkg = governance_package_service.create(db_session, payload)
    result = governance_package_service.validate(db_session, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(
        db_session, ORG, pkg.id, approver_principal_id="tester", rationale="test"
    )
    governance_package_service.publish(db_session, ORG, pkg.id)
    return pkg


def _control(**overrides):
    control = {
        "control_id": CIRCLE_CONTROL_ID,
        "applicability": "APPLICABLE",
        "result": "SATISFIED",
        "evidence_sufficiency": "SUFFICIENT",
        "evidence_freshness": "FRESH",
        "monitoring_status": "CURRENT",
        "assessment_id": "assessment-1",
        "decision_id": "decision-1",
        "proof_id": "proof-1",
        "proof_hash": "hash-1",
        "proof_status": "ACTIVE",
        "last_evaluated_at": "2026-09-23T00:00:00Z",
    }
    control.update(overrides)
    return control


def _registry_for(handler) -> ConnectorRegistry:
    connector = CompliLedgerAssuranceConnector(
        base_url="http://compliledger.test",
        http_client=httpx.Client(
            base_url="http://compliledger.test",
            transport=httpx.MockTransport(handler),
        ),
    )
    return ConnectorRegistry([connector])


def _healthy_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"target_id": "target_lusd", "controls": [_control()]}
    )


def _degraded_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "target_id": "target_lusd",
            "controls": [_control(result="NOT_EVALUABLE", monitoring_status="STALE")],
        },
    )


def _unreachable_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def _propose(db, *, registry, amount_minor, action="USDC_TRANSFER", network="ARC"):
    return governed_action_service.propose(
        db,
        ORG,
        actor_id=seed.CIRCLE_TREASURY_AGENT_ID,
        intent_type=IntentType.TRANSFER,
        action=action,
        compliidentity_resource="circle.treasury_action",
        compliidentity_action="propose",
        resource_instance=RECIPIENT,
        target_identifier=RECIPIENT,
        rationale="treasury transfer",
        amount_minor=amount_minor,
        amount_currency="USDC",
        extra_parameters={"asset": "USDC", "network": network},
        registry=registry,
    )


def _reason_codes(decision) -> list[str]:
    return json.loads(decision.reason_codes)


# --------------------------------------------------------------------------- #
# The 5 scenarios required by the PR 3a prompt
# --------------------------------------------------------------------------- #
def test_healthy_assurance_5_usdc_approves_and_authorization_issuable(
    db_session, published_package
):
    result = _propose(
        db_session,
        registry=_registry_for(_healthy_handler),
        amount_minor=FIVE_USDC_MINOR,
    )
    assert result.decision.outcome == DecisionOutcome.APPROVED.value
    assert "AUTHORIZED_WITHIN_LIMIT" in _reason_codes(result.decision)

    auth = authorization_service.issue(db_session, ORG, result.decision.id)
    assert auth is not None


def test_healthy_assurance_25_usdc_escalates_and_issue_raises_conflict(
    db_session, published_package
):
    result = _propose(
        db_session,
        registry=_registry_for(_healthy_handler),
        amount_minor=TWENTY_FIVE_USDC_MINOR,
    )
    assert result.decision.outcome == DecisionOutcome.ESCALATED.value
    assert "AUTONOMOUS_LIMIT_EXCEEDED" in _reason_codes(result.decision)

    with pytest.raises(ConflictError):
        authorization_service.issue(db_session, ORG, result.decision.id)


def test_degraded_assurance_5_usdc_denies_not_escalates(db_session, published_package):
    # _degraded_handler returns result="NOT_EVALUABLE", monitoring_status="STALE".
    result = _propose(
        db_session,
        registry=_registry_for(_degraded_handler),
        amount_minor=FIVE_USDC_MINOR,
    )
    reasons = _reason_codes(result.decision)
    assert result.decision.outcome == DecisionOutcome.DENIED.value
    assert result.decision.outcome != DecisionOutcome.ESCALATED.value
    assert "REQUIRED_ASSURANCE_NOT_EVALUABLE" in reasons


def test_not_satisfied_assurance_5_usdc_denies_required_assurance_not_satisfied(
    db_session, published_package
):
    result = _propose(
        db_session,
        registry=_registry_for(
            lambda request: httpx.Response(
                200,
                json={
                    "target_id": "target_lusd",
                    "controls": [_control(result="NOT_SATISFIED")],
                },
            )
        ),
        amount_minor=FIVE_USDC_MINOR,
    )
    reasons = _reason_codes(result.decision)
    assert result.decision.outcome == DecisionOutcome.DENIED.value
    assert result.decision.outcome != DecisionOutcome.ESCALATED.value
    assert "REQUIRED_ASSURANCE_NOT_SATISFIED" in reasons


def test_compliledger_unreachable_5_usdc_denies_via_required_assurance_condition(
    db_session, published_package
):
    result = _propose(
        db_session,
        registry=_registry_for(_unreachable_handler),
        amount_minor=FIVE_USDC_MINOR,
    )
    reasons = _reason_codes(result.decision)
    triggered = json.loads(result.decision.decision_conditions_triggered)
    triggered_codes = {c.get("reason_code") for c in triggered}

    assert result.decision.outcome == DecisionOutcome.DENIED.value
    assert result.decision.outcome != DecisionOutcome.ESCALATED.value
    assert "REQUIRED_ASSURANCE_UNAVAILABLE" in reasons
    # Must have denied via a DC-CIRCLE-ASSURANCE-* condition, not the generic
    # MANDATORY_CONTROL_FAILED fallback path.
    assert "MANDATORY_CONTROL_FAILED" not in reasons
    assert any(
        str(cid).startswith("DC-CIRCLE-ASSURANCE-")
        for cid in {c.get("condition_id") for c in triggered}
    )
    assert "REQUIRED_ASSURANCE_UNAVAILABLE" in triggered_codes


def test_wrong_network_5_usdc_denies_delegated_authority_exceeded(
    db_session, published_package
):
    result = _propose(
        db_session,
        registry=_registry_for(_healthy_handler),
        amount_minor=FIVE_USDC_MINOR,
        network="ETH",
    )
    assert result.decision.outcome == DecisionOutcome.DENIED.value
    assert "DELEGATED_AUTHORITY_EXCEEDED" in _reason_codes(result.decision)
    triggered = json.loads(result.decision.decision_conditions_triggered)
    assert any(
        str(c.get("condition_id")).startswith("DC-AGT-AUTH-001-")
        for c in triggered
    )


# --------------------------------------------------------------------------- #
# Additional coverage for priorities 20 / 30 (action) -- these enforce the
# AGT-AUTH-001 control's verified/not-revoked/in-scope judgment (module
# docstring in circle_treasury_package.py).
# --------------------------------------------------------------------------- #
def test_revoked_actor_5_usdc_denies_actor_not_verified(db_session, published_package):
    actor = db_session.get(ActorIdentity, seed.CIRCLE_TREASURY_AGENT_ID)
    actor.revocation_status = "REVOKED"
    db_session.commit()

    result = _propose(
        db_session,
        registry=_registry_for(_healthy_handler),
        amount_minor=FIVE_USDC_MINOR,
    )
    assert result.decision.outcome == DecisionOutcome.DENIED.value
    assert "ACTOR_NOT_VERIFIED" in _reason_codes(result.decision)
    triggered = json.loads(result.decision.decision_conditions_triggered)
    assert any(
        str(c.get("condition_id")).startswith("DC-AGT-AUTH-001-")
        for c in triggered
    )


def test_disallowed_action_5_usdc_denies_delegated_authority_exceeded(
    db_session, published_package
):
    result = _propose(
        db_session,
        registry=_registry_for(_healthy_handler),
        amount_minor=FIVE_USDC_MINOR,
        action="WIRE_TRANSFER",
    )
    assert result.decision.outcome == DecisionOutcome.DENIED.value
    assert "DELEGATED_AUTHORITY_EXCEEDED" in _reason_codes(result.decision)


def test_healthy_assurance_5_usdc_control_evaluations_reference_agt_auth_001(
    db_session, published_package
):
    """The decision's control evaluations include the new AGT-AUTH-001
    control -- a formal, standalone control, not a reference to
    CTL-CIRCLE-LUSD-ASSURANCE or any pre-existing control."""
    from app.services.canonical import control_evaluation_service

    result = _propose(
        db_session,
        registry=_registry_for(_healthy_handler),
        amount_minor=FIVE_USDC_MINOR,
    )
    assert result.decision.outcome == DecisionOutcome.APPROVED.value

    evaluations = control_evaluation_service.list_for_resolution(
        db_session, ORG, result.policy_resolution.id
    )
    control_ids = {ce.control_id for ce in evaluations}
    assert "AGT-AUTH-001" in control_ids
    assert "CTL-CIRCLE-LUSD-ASSURANCE" in control_ids

    agt_auth = next(ce for ce in evaluations if ce.control_id == "AGT-AUTH-001")
    assert agt_auth.result == "SATISFIED"
    assert agt_auth.mandatory is True


# --------------------------------------------------------------------------- #
# API-level: the route is thin and wired end to end
# --------------------------------------------------------------------------- #
def test_route_proposes_governed_action(api_client, monkeypatch):
    from app.core.database import get_db
    from app.db import seed as seed_module
    from app.services.canonical import governed_action_service as gas_module

    # Seed org/actor/package against the same engine the TestClient uses.

    override = api_client.app.dependency_overrides[get_db]
    db = next(override())
    try:
        seed_module.seed_organizations(db)
        seed_module.seed_circle_treasury_agent(db)
        payload = build_circle_treasury_package(ORG)
        pkg = governance_package_service.create(db, payload)
        governance_package_service.validate(db, ORG, pkg.id)
        governance_package_service.approve(
            db, ORG, pkg.id, approver_principal_id="tester", rationale="test"
        )
        governance_package_service.publish(db, ORG, pkg.id)
    finally:
        db.close()

    monkeypatch.setattr(
        gas_module,
        "default_production_registry",
        lambda: _registry_for(_healthy_handler),
    )

    response = api_client.post(
        "/api/v1/governed-actions",
        json={
            "actor_id": seed.CIRCLE_TREASURY_AGENT_ID,
            "amount_minor": FIVE_USDC_MINOR,
            "target_identifier": RECIPIENT,
        },
        headers={"X-Organization-Id": ORG},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["outcome"] == DecisionOutcome.APPROVED.value
    assert "AUTHORIZED_WITHIN_LIMIT" in body["reason_codes"]
