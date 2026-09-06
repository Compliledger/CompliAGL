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

from app.services.canonical import decision_service, escalation_approval_service
from app.services.canonical.authority_context_service import AuthorityContext
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
