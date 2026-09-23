"""Tests for the Circle treasury governance package content and publication."""

from __future__ import annotations

from app.db import seed
from app.db.circle_treasury_package import build_circle_treasury_package
from app.services.canonical import governance_package_service

ORG = "circle-mvp-demo"


def test_package_validates_and_publishes(db_session):
    seed.seed_organizations(db_session)
    payload = build_circle_treasury_package(ORG)
    pkg = governance_package_service.create(db_session, payload)
    result = governance_package_service.validate(db_session, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(
        db_session, ORG, pkg.id, approver_principal_id="tester", rationale="test"
    )
    published = governance_package_service.publish(db_session, ORG, pkg.id)
    assert published.status == "PUBLISHED"
    assert published.requires_authority_context is False


def test_decision_condition_priorities_and_reason_codes():
    payload = build_circle_treasury_package(ORG)
    by_priority = {c.priority: c for c in payload.decision_conditions}
    assert by_priority[10].reason_code == "REQUIRED_ASSURANCE_UNAVAILABLE"
    assert by_priority[10].resulting_decision == "DENIED"
    assert by_priority[11].reason_code == "REQUIRED_ASSURANCE_NOT_EVALUABLE"
    assert by_priority[11].resulting_decision == "DENIED"
    assert by_priority[12].reason_code == "REQUIRED_ASSURANCE_NOT_SATISFIED"
    assert by_priority[12].resulting_decision == "DENIED"
    assert by_priority[13].reason_code == "REQUIRED_ASSURANCE_STALE"
    assert by_priority[13].resulting_decision == "DENIED"
    assert by_priority[20].reason_code == "ACTOR_NOT_VERIFIED"
    assert by_priority[20].resulting_decision == "DENIED"
    assert by_priority[30].reason_code == "DELEGATED_AUTHORITY_EXCEEDED"
    assert by_priority[30].resulting_decision == "DENIED"
    assert by_priority[40].reason_code == "AUTONOMOUS_LIMIT_EXCEEDED"
    assert by_priority[40].resulting_decision == "ESCALATED"
    assert by_priority[50].reason_code == "AUTHORIZED_WITHIN_LIMIT"
    assert by_priority[50].resulting_decision == "APPROVED"
    assert all(c.terminal for c in payload.decision_conditions)


def test_evidence_requirement_is_mandatory():
    payload = build_circle_treasury_package(ORG)
    assert len(payload.evidence_requirements) == 1
    req = payload.evidence_requirements[0]
    assert req.mandatory is True
    assert req.evidence_type == "compliledger.assurance_state.v1"


def test_control_expression_is_structural_not_business_content():
    payload = build_circle_treasury_package(ORG)
    control = payload.control_definitions[0]
    assert control.mandatory is True
    assert "result" not in control.evaluation_expression
    assert "monitoring_status" not in control.evaluation_expression
    assert "control_id" in control.evaluation_expression


def test_agent_authority_is_a_new_formal_control():
    payload = build_circle_treasury_package(ORG)
    by_id = {c.control_id: c for c in payload.control_definitions}
    assert "AGT-AUTH-001" in by_id
    control = by_id["AGT-AUTH-001"]
    assert control.mandatory is True
    assert control.control_id not in ("AAI-001", "AAI-002", "AAI-003")
    # A new control, not a reference to the assurance control.
    assert control.control_id != "CTL-CIRCLE-LUSD-ASSURANCE"

    req_ids = {r.requirement_id for r in payload.requirements}
    assert set(control.requirement_ids).issubset(req_ids)
