"""Commit 4 -- the ``approval`` runtime fact + re-decision.

Drives the real pipeline to an ESCALATED decision, submits an authority-verified
escalation approval, then re-decides with ``prior_decision_id`` and checks the
package condition upgrades the escalation off the ``approval`` fact -- the prior
decision preserved and superseded, the approval consumed, ``approval_hash``
bound into the new decision.

Also covers part (a): ``Decision.required_approver_types`` persisted from the
authority context at decision time.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from app.core.database import get_db
from app.main import app
from app.services.canonical import decision_service, escalation_approval_service
from app.services.canonical.authority_context_service import AuthorityContext
from app.services.canonical.errors import ConflictError, NotFoundError
from app.utils.canonical_enums import (
    DecisionOutcome,
    DecisionSupersessionStatus,
    EscalationApprovalStatus,
)
from app.utils.timestamps import utc_now
from tests.test_decision_authorization import ORG, _run_pipeline

# Priority order: an approval upgrades first; absent/expired approval falls
# through to the authority-driven escalation.
_CONDITIONS = [
    {
        "condition_id": "DC-APPROVE-VIA-APPROVAL",
        "expression": "approval.present == True and approval.expired == False",
        "resulting_decision": "APPROVED",
        "priority": 10,
        "reason_code": "APPROVED_VIA_HUMAN_APPROVAL",
        "terminal": True,
    },
    {
        "condition_id": "DC-ESCALATE",
        "expression": "authority.approval_required == True",
        "resulting_decision": "ESCALATED",
        "priority": 20,
        "reason_code": "HUMAN_APPROVAL_REQUIRED",
        "terminal": True,
    },
    {
        "condition_id": "DC-APPROVE-DEFAULT",
        "expression": "True",
        "resulting_decision": "APPROVED",
        "priority": 100,
        "reason_code": "APPROVED_OK",
        "terminal": True,
    },
]

_APPROVER = "jordan-human-principal"


class _ActionAwareClient:
    """Fake authority client that answers per probed ``action`` -- CompliIdentity
    genuinely returns different things for propose vs approve."""

    def __init__(self, by_action: dict, default: AuthorityContext):
        self._by_action = by_action
        self._default = default
        self.calls: list[dict] = []

    def fetch(self, **kwargs):
        self.calls.append(kwargs)
        return self._by_action.get(kwargs.get("action"), self._default)


def _escalate_ctx(applicable_approvals=()) -> AuthorityContext:
    return AuthorityContext(
        status="OK",
        reason="approval_required",
        sufficient=False,
        approval_required=True,
        findings=("permission_present", "approval_required"),
        applicable_approvals=tuple(applicable_approvals),
    )


def _approve_ctx() -> AuthorityContext:
    return AuthorityContext(
        status="OK",
        sufficient=True,
        permission_present=True,
        findings=("permission_present",),
        raw={"principal_type": "HUMAN",
             "authority_for_request": {"sufficient": True}},
    )


def _patch(monkeypatch, client) -> None:
    monkeypatch.setattr(
        "app.services.canonical.authority_context_service.default_client",
        lambda **kw: client,
    )


# --------------------------------------------------------------------------- #
def test_reevaluation_with_approval_upgrades_escalation(db_session, monkeypatch):
    client = _ActionAwareClient({"approve": _approve_ctx()}, _escalate_ctx())
    _patch(monkeypatch, client)

    resolution, actor, _target, _assessment = _run_pipeline(
        db_session, _CONDITIONS, requires_authority_context=True
    )
    d1 = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    assert d1.outcome == DecisionOutcome.ESCALATED.value
    assert d1.approval_hash is None

    approval = escalation_approval_service.submit(
        db_session,
        ORG,
        decision_id=d1.id,
        approver_principal_id=_APPROVER,
        rationale="Case reviewed; approver authority verified.",
    )

    d2 = decision_service.decide_for_resolution(
        db_session, ORG, resolution.id, prior_decision_id=d1.id
    )
    assert d2.outcome == DecisionOutcome.APPROVED.value
    assert "APPROVED_VIA_HUMAN_APPROVAL" in json.loads(d2.reason_codes)
    # New decision, prior preserved + linked both ways.
    assert d2.id != d1.id
    assert d2.prior_decision_id == d1.id
    refreshed_d1 = decision_service.get(db_session, ORG, d1.id)
    assert refreshed_d1.supersession_status == (
        DecisionSupersessionStatus.SUPERSEDED.value
    )
    assert refreshed_d1.superseded_by_decision_id == d2.id
    # approval_hash bound into the re-decision.
    assert d2.approval_hash is not None
    assert d2.input_hash != d1.input_hash
    # The approval is spent.
    refreshed = escalation_approval_service.get(db_session, ORG, approval.id)
    assert refreshed.status == EscalationApprovalStatus.CONSUMED.value
    assert refreshed.consumed_by_decision_id == d2.id


def test_reevaluation_with_expired_approval_stays_escalated(db_session, monkeypatch):
    client = _ActionAwareClient({"approve": _approve_ctx()}, _escalate_ctx())
    _patch(monkeypatch, client)

    resolution, _actor, _t, _a = _run_pipeline(
        db_session, _CONDITIONS, requires_authority_context=True
    )
    d1 = decision_service.decide_for_resolution(db_session, ORG, resolution.id)

    approval = escalation_approval_service.submit(
        db_session,
        ORG,
        decision_id=d1.id,
        approver_principal_id=_APPROVER,
        rationale="approved, but with a window that has already closed",
        valid_until=utc_now() - timedelta(seconds=1),
    )

    d2 = decision_service.decide_for_resolution(
        db_session, ORG, resolution.id, prior_decision_id=d1.id
    )
    assert d2.outcome == DecisionOutcome.ESCALATED.value
    # An expired approval is not consumed.
    refreshed = escalation_approval_service.get(db_session, ORG, approval.id)
    assert refreshed.status == EscalationApprovalStatus.ACTIVE.value
    assert refreshed.consumed_by_decision_id is None


def test_decision_persists_required_approver_types_from_authority(
    db_session, monkeypatch
):
    # Persistence plumbing: authority context -> Decision.required_approver_types
    # -> explain() -> submit() cross-check. That the parsed value traces to
    # CompliIdentity's *real* applicable_approvals[].approver_principal_type is
    # proved separately in test_authority_context_service
    # (test_required_approver_types_distilled_from_real_body).
    # _run_pipeline's param-less intent probes with action "request".
    client = _ActionAwareClient(
        {"approve": _approve_ctx()},
        _escalate_ctx(
            applicable_approvals=[
                {"resource": "PAYMENT", "action": "request",
                 "approver_principal_type": "HUMAN"}
            ]
        ),
    )
    _patch(monkeypatch, client)

    resolution, _actor, _t, _a = _run_pipeline(
        db_session, _CONDITIONS, requires_authority_context=True
    )
    d1 = decision_service.decide_for_resolution(db_session, ORG, resolution.id)

    assert json.loads(d1.required_approver_types) == ["HUMAN"]
    explanation = decision_service.explain(db_session, ORG, d1.id)
    assert explanation["required_approver_types"] == ["HUMAN"]

    # A HUMAN approver satisfies the persisted required type.
    approval = escalation_approval_service.submit(
        db_session,
        ORG,
        decision_id=d1.id,
        approver_principal_id=_APPROVER,
        rationale="human approver matches CompliIdentity's required type",
    )
    assert approval.approver_principal_type == "HUMAN"


def test_first_decision_without_prior_has_no_approval_fact(db_session, monkeypatch):
    client = _ActionAwareClient({"approve": _approve_ctx()}, _escalate_ctx())
    _patch(monkeypatch, client)
    resolution, _actor, _t, _a = _run_pipeline(
        db_session, _CONDITIONS, requires_authority_context=True
    )
    d1 = decision_service.decide_for_resolution(db_session, ORG, resolution.id)
    explanation = decision_service.explain(db_session, ORG, d1.id)
    assert explanation["input_hashes"]["approval_hash"] is None


# --------------------------------------------------------------------------- #
# escalation_approval_service.apply() -- the step-2 orchestration wrapper
# --------------------------------------------------------------------------- #
def _escalated_with_approval(db, monkeypatch):
    client = _ActionAwareClient({"approve": _approve_ctx()}, _escalate_ctx())
    _patch(monkeypatch, client)
    resolution, _actor, _t, _a = _run_pipeline(
        db, _CONDITIONS, requires_authority_context=True
    )
    d1 = decision_service.decide_for_resolution(db, ORG, resolution.id)
    assert d1.outcome == DecisionOutcome.ESCALATED.value
    approval = escalation_approval_service.submit(
        db,
        ORG,
        decision_id=d1.id,
        approver_principal_id=_APPROVER,
        rationale="reviewed; approver authority verified",
    )
    return d1, approval


def test_apply_reevaluates_and_upgrades_the_escalation(db_session, monkeypatch):
    d1, approval = _escalated_with_approval(db_session, monkeypatch)

    d2 = escalation_approval_service.apply(
        db_session, ORG, escalation_approval_id=approval.id
    )
    assert d2.outcome == DecisionOutcome.APPROVED.value
    assert d2.prior_decision_id == d1.id
    refreshed = escalation_approval_service.get(db_session, ORG, approval.id)
    assert refreshed.status == EscalationApprovalStatus.CONSUMED.value
    assert refreshed.consumed_by_decision_id == d2.id


def test_apply_rejects_an_already_consumed_approval(db_session, monkeypatch):
    _d1, approval = _escalated_with_approval(db_session, monkeypatch)
    escalation_approval_service.apply(
        db_session, ORG, escalation_approval_id=approval.id
    )
    with pytest.raises(ConflictError):
        escalation_approval_service.apply(
            db_session, ORG, escalation_approval_id=approval.id
        )


def test_apply_unknown_approval_raises_not_found(db_session):
    with pytest.raises(NotFoundError):
        escalation_approval_service.apply(
            db_session, ORG, escalation_approval_id="EAP-nope"
        )


# --------------------------------------------------------------------------- #
# API: POST /escalation-approvals  ->  GET  ->  POST .../apply
# --------------------------------------------------------------------------- #
def _api_db():
    return next(app.dependency_overrides[get_db]())


def _seed_escalated_into_api_db(monkeypatch) -> str:
    """Run the real pipeline to an ESCALATED-by-policy decision in the API's
    DB; return the decision id."""
    db = _api_db()
    try:
        client = _ActionAwareClient({"approve": _approve_ctx()}, _escalate_ctx())
        _patch(monkeypatch, client)
        resolution, _a, _t, _as = _run_pipeline(
            db, _CONDITIONS, requires_authority_context=True
        )
        d1 = decision_service.decide_for_resolution(db, ORG, resolution.id)
        assert d1.outcome == DecisionOutcome.ESCALATED.value
        return d1.id
    finally:
        db.close()


def test_api_escalation_approval_submit_get_apply_flow(api_client, monkeypatch):
    d1_id = _seed_escalated_into_api_db(monkeypatch)
    headers = {"X-Organization-Id": ORG}

    resp = api_client.post(
        "/api/v1/escalation-approvals",
        json={
            "organization_id": ORG,
            "decision_id": d1_id,
            "approver_principal_id": _APPROVER,
            "rationale": "Reviewed the case; approver authority verified.",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["approver_principal_type"] == "HUMAN"
    assert body["status"] == EscalationApprovalStatus.ACTIVE.value
    approval_id = body["id"]

    assert (
        api_client.get(
            f"/api/v1/escalation-approvals/{approval_id}", headers=headers
        ).status_code
        == 200
    )
    listed = api_client.get(
        f"/api/v1/escalation-approvals?decision_id={d1_id}", headers=headers
    )
    assert listed.status_code == 200 and len(listed.json()) == 1

    applied = api_client.post(
        f"/api/v1/escalation-approvals/{approval_id}/apply", headers=headers
    )
    assert applied.status_code == 201, applied.text
    new_decision = applied.json()
    assert new_decision["outcome"] == DecisionOutcome.APPROVED.value
    assert new_decision["prior_decision_id"] == d1_id

    # The approval is spent -> re-applying is a 409.
    again = api_client.post(
        f"/api/v1/escalation-approvals/{approval_id}/apply", headers=headers
    )
    assert again.status_code == 409


def test_api_submit_rejects_unverified_approver_with_422(api_client, monkeypatch):
    d1_id = _seed_escalated_into_api_db(monkeypatch)
    # Re-point the fake so the approve probe now comes back not-sufficient.
    _patch(
        monkeypatch,
        _ActionAwareClient(
            {"approve": AuthorityContext(status="OK", sufficient=False,
                                         raw={"principal_type": "HUMAN"})},
            _escalate_ctx(),
        ),
    )
    resp = api_client.post(
        "/api/v1/escalation-approvals",
        json={
            "organization_id": ORG,
            "decision_id": d1_id,
            "approver_principal_id": _APPROVER,
            "rationale": "approver lacks the grant",
        },
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["reason"] == "not_sufficient"


def test_api_submit_on_non_escalated_decision_is_409(api_client, monkeypatch):
    db = _api_db()
    try:
        client = _ActionAwareClient({"approve": _approve_ctx()}, _approve_ctx())
        _patch(monkeypatch, client)
        # authority sufficient + amount clause absent -> APPROVED, not escalated.
        resolution, _a, _t, _as = _run_pipeline(
            db,
            [{"condition_id": "DC-OK", "expression": "True",
              "resulting_decision": "APPROVED", "priority": 100,
              "reason_code": "OK", "terminal": True}],
            requires_authority_context=True,
        )
        d = decision_service.decide_for_resolution(db, ORG, resolution.id)
        assert d.outcome == DecisionOutcome.APPROVED.value
        d_id = d.id
    finally:
        db.close()
    resp = api_client.post(
        "/api/v1/escalation-approvals",
        json={
            "organization_id": ORG,
            "decision_id": d_id,
            "approver_principal_id": _APPROVER,
            "rationale": "not an escalation",
        },
    )
    assert resp.status_code == 409, resp.text
