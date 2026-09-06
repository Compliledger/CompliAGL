"""Tests for escalation-approval step 1: authority-verified human approval.

Covers ``authority_context_service.verify_approver_authority`` (the shared
fail-closed approver check) and ``escalation_approval_service.submit`` (records
an ACTIVE approval only when that check passes; never re-decides).
"""

from __future__ import annotations

import json

import pytest

from app.models.decision import Decision
from app.models.policy_resolution import PolicyResolution
from app.repositories.canonical import DecisionRepository, PolicyResolutionRepository
from app.schemas.canonical.actor_identity import ActorIdentityCreate
from app.schemas.canonical.intent import IntentCreate
from app.services.canonical import (
    actor_identity_service,
    authority_context_service,
    escalation_approval_service,
    intent_service,
)
from app.services.canonical.authority_context_service import AuthorityContext
from app.services.canonical.errors import (
    AuthorityVerificationError,
    ConflictError,
    NotFoundError,
)
from app.utils.canonical_enums import (
    CanonicalActorType,
    DecisionOutcome,
    DecisionSupersessionStatus,
    EscalationApprovalStatus,
    IntentType,
)
from app.utils.timestamps import utc_now

ORG = "org-escalation-approval"

_CASE = "HARBORSTONE-2024-0042"
_AMOUNT_MINOR = 25_000_000


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _FakeAuthorityClient:
    def __init__(self, context: AuthorityContext):
        self._context = context
        self.calls: list[dict] = []

    def fetch(self, **kwargs):
        self.calls.append(kwargs)
        return self._context


def _human_sufficient_ctx(**raw_overrides) -> AuthorityContext:
    raw = {
        "principal_type": "HUMAN",
        "principal": {"principal_type": "HUMAN", "status": "ACTIVE"},
        "authority_for_request": {
            "sufficient": True,
            "permission_present": True,
            "approval_required": False,
            "applicable_approvals": [],
            "findings": ["permission_present"],
        },
    }
    raw.update(raw_overrides)
    return AuthorityContext(
        status="OK",
        sufficient=True,
        permission_present=True,
        approval_required=False,
        findings=("permission_present",),
        raw=raw,
    )


def _patch_client(monkeypatch, client) -> None:
    monkeypatch.setattr(
        authority_context_service, "default_client", lambda **kw: client
    )


# --------------------------------------------------------------------------- #
# verify_approver_authority
# --------------------------------------------------------------------------- #
def _verify(client, **overrides):
    kw = dict(
        organization_id=ORG,
        approver_principal_id="principal-jordan",
        resource="aml.action",
        action="approve",
        resource_instance=_CASE,
        attribute="amount",
        value=str(_AMOUNT_MINOR),
    )
    kw.update(overrides)
    return authority_context_service.verify_approver_authority(client, **kw)


def test_verify_authorized_when_sufficient_and_human():
    result = _verify(_FakeAuthorityClient(_human_sufficient_ctx()))
    assert result.authorized is True
    assert result.reason == "authorized"
    assert result.approver_principal_type == "HUMAN"


def test_verify_rejects_unconfigured_client():
    result = _verify(None)
    assert result.authorized is False
    assert result.reason == "client_unconfigured"


def test_verify_rejects_unavailable_context():
    ctx = AuthorityContext(status="UNAVAILABLE", reason="timeout")
    result = _verify(_FakeAuthorityClient(ctx))
    assert result.authorized is False
    assert result.reason == "authority_unavailable"


def test_verify_rejects_known_denied_context():
    ctx = AuthorityContext(status="KNOWN_DENIED", reason="principal_not_found")
    result = _verify(_FakeAuthorityClient(ctx))
    assert result.authorized is False
    assert result.reason == "authority_known_denied"


def test_verify_rejects_not_sufficient():
    ctx = AuthorityContext(
        status="OK",
        sufficient=False,
        findings=("permission_missing",),
        raw={"principal_type": "HUMAN"},
    )
    result = _verify(_FakeAuthorityClient(ctx))
    assert result.authorized is False
    assert result.reason == "not_sufficient"


def test_verify_rejects_non_human_approver_even_when_sufficient():
    ctx = _human_sufficient_ctx(
        principal_type="AI_AGENT",
        principal={"principal_type": "AI_AGENT", "status": "ACTIVE"},
    )
    result = _verify(_FakeAuthorityClient(ctx))
    assert result.authorized is False
    assert result.reason == "approver_not_human"
    assert result.approver_principal_type == "AI_AGENT"


# --------------------------------------------------------------------------- #
# escalation_approval_service.submit
# --------------------------------------------------------------------------- #
def _escalated_decision(
    db,
    *,
    outcome=None,
    reason_codes=None,
    supersession=None,
    required_approver_types=None,
):
    actor = actor_identity_service.create(
        db,
        ActorIdentityCreate(
            organization_id=ORG,
            actor_type=CanonicalActorType.AI_AGENT,
            wallet_or_agent_account_id="agent-aira",
        ),
    )
    intent = intent_service.create(
        db,
        IntentCreate(
            organization_id=ORG,
            intent_type=IntentType.PAYMENT,
            action="propose",
            actor_id=actor.id,
            amount_minor=_AMOUNT_MINOR,
            amount_currency="USD",
            parameters={
                "compliidentity_resource": "aml.action",
                "compliidentity_action": "propose",
                "compliidentity_resource_instance": _CASE,
            },
        ),
    )
    resolution = PolicyResolutionRepository(db).add(
        PolicyResolution(
            organization_id=ORG,
            actor_identity_id=actor.id,
            intent_id=intent.id,
            engine_version="test",
        )
    )
    decision = DecisionRepository(db).add(
        Decision(
            organization_id=ORG,
            governance_evaluation_id=resolution.id,
            intent_id=intent.id,
            evaluation_id=resolution.id,
            policy_resolution_id=resolution.id,
            outcome=(outcome or DecisionOutcome.ESCALATED.value),
            reason_codes=json.dumps(
                reason_codes
                if reason_codes is not None
                else [
                    "DECISION_ESCALATED",
                    "ESCALATED_BY_POLICY",
                    "HUMAN_APPROVAL_REQUIRED",
                ]
            ),
            decision_conditions_triggered="[]",
            decision_hash="dh-esc-approval",
            required_approver_types=(
                json.dumps(required_approver_types)
                if required_approver_types
                else None
            ),
            supersession_status=(
                supersession or DecisionSupersessionStatus.CURRENT.value
            ),
            decided_at=utc_now(),
        )
    )
    return actor, intent, decision


def test_submit_records_active_authority_verified_approval(db_session, monkeypatch):
    _, intent, decision = _escalated_decision(db_session)
    client = _FakeAuthorityClient(_human_sufficient_ctx())
    _patch_client(monkeypatch, client)

    approval = escalation_approval_service.submit(
        db_session,
        ORG,
        decision_id=decision.id,
        approver_principal_id="principal-jordan",
        rationale="Reviewed the case file; approve authority verified.",
    )

    assert approval.status == EscalationApprovalStatus.ACTIVE.value
    assert approval.decision_id == decision.id
    assert approval.intent_id == intent.id
    assert approval.approver_principal_id == "principal-jordan"
    assert approval.approver_principal_type == "HUMAN"
    assert approval.approver_authority_hash  # bound the verified snapshot
    assert approval.approval_hash
    assert approval.escalation_approval_id == "EAP-" + approval.approval_hash[:16]
    assert approval.consumed_by_decision_id is None
    assert approval.valid_until > approval.granted_at

    # The probe was made for the approver, action forced to "approve", same
    # case + amount as the intent.
    (probe,) = client.calls
    assert probe["principal_id"] == "principal-jordan"
    assert probe["action"] == "approve"
    assert probe["resource"] == "aml.action"
    assert probe["resource_instance"] == _CASE
    assert probe["value"] == str(_AMOUNT_MINOR)


def test_submit_rejects_self_approval(db_session, monkeypatch):
    _, _, decision = _escalated_decision(db_session)
    _patch_client(monkeypatch, _FakeAuthorityClient(_human_sufficient_ctx()))

    with pytest.raises(AuthorityVerificationError) as exc:
        escalation_approval_service.submit(
            db_session,
            ORG,
            decision_id=decision.id,
            approver_principal_id="agent-aira",  # == the actor's principal id
            rationale="trying to approve my own escalation",
        )
    assert exc.value.reason == "self_approval"


def test_submit_rejects_when_authority_not_sufficient(db_session, monkeypatch):
    _, _, decision = _escalated_decision(db_session)
    ctx = AuthorityContext(
        status="OK", sufficient=False, raw={"principal_type": "HUMAN"}
    )
    _patch_client(monkeypatch, _FakeAuthorityClient(ctx))

    with pytest.raises(AuthorityVerificationError) as exc:
        escalation_approval_service.submit(
            db_session,
            ORG,
            decision_id=decision.id,
            approver_principal_id="principal-jordan",
            rationale="approver lacks the grant",
        )
    assert exc.value.reason == "not_sufficient"
    assert escalation_approval_service.list_for_decision(
        db_session, ORG, decision.id
    ) == []


def test_submit_rejects_when_client_unconfigured(db_session, monkeypatch):
    _, _, decision = _escalated_decision(db_session)
    _patch_client(monkeypatch, None)

    with pytest.raises(AuthorityVerificationError) as exc:
        escalation_approval_service.submit(
            db_session,
            ORG,
            decision_id=decision.id,
            approver_principal_id="principal-jordan",
            rationale="no CompliIdentity configured",
        )
    assert exc.value.reason == "client_unconfigured"


def test_submit_rejects_non_escalated_decision(db_session, monkeypatch):
    _, _, decision = _escalated_decision(
        db_session,
        outcome=DecisionOutcome.APPROVED.value,
        reason_codes=["DECISION_APPROVED", "APPROVED_BY_POLICY"],
    )
    _patch_client(monkeypatch, _FakeAuthorityClient(_human_sufficient_ctx()))

    with pytest.raises(ConflictError):
        escalation_approval_service.submit(
            db_session,
            ORG,
            decision_id=decision.id,
            approver_principal_id="principal-jordan",
            rationale="not an escalation",
        )


def test_submit_rejects_escalation_without_policy_condition(db_session, monkeypatch):
    # ESCALATED but not ESCALATED_BY_POLICY (e.g. an assessment-driven
    # escalation) -> not the approval path.
    _, _, decision = _escalated_decision(
        db_session,
        reason_codes=["DECISION_ESCALATED", "ASSESSMENT_MANUAL_REVIEW_REQUIRED"],
    )
    _patch_client(monkeypatch, _FakeAuthorityClient(_human_sufficient_ctx()))

    with pytest.raises(ConflictError):
        escalation_approval_service.submit(
            db_session,
            ORG,
            decision_id=decision.id,
            approver_principal_id="principal-jordan",
            rationale="wrong escalation kind",
        )


def test_submit_rejects_superseded_decision(db_session, monkeypatch):
    _, _, decision = _escalated_decision(
        db_session, supersession=DecisionSupersessionStatus.SUPERSEDED.value
    )
    _patch_client(monkeypatch, _FakeAuthorityClient(_human_sufficient_ctx()))

    with pytest.raises(ConflictError):
        escalation_approval_service.submit(
            db_session,
            ORG,
            decision_id=decision.id,
            approver_principal_id="principal-jordan",
            rationale="already superseded",
        )


def test_submit_unknown_decision_raises_not_found(db_session, monkeypatch):
    _patch_client(monkeypatch, _FakeAuthorityClient(_human_sufficient_ctx()))
    with pytest.raises(NotFoundError):
        escalation_approval_service.submit(
            db_session,
            ORG,
            decision_id="DEC-nope",
            approver_principal_id="principal-jordan",
            rationale="no such decision",
        )


# --- Decision.required_approver_types cross-check (commit 4 part b) --------- #
def test_submit_accepts_matching_required_approver_type(db_session, monkeypatch):
    _, _, decision = _escalated_decision(
        db_session, required_approver_types=["HUMAN"]
    )
    _patch_client(monkeypatch, _FakeAuthorityClient(_human_sufficient_ctx()))

    approval = escalation_approval_service.submit(
        db_session,
        ORG,
        decision_id=decision.id,
        approver_principal_id="principal-jordan",
        rationale="human approver matches the required type",
    )
    assert approval.approver_principal_type == "HUMAN"


def test_submit_rejects_when_approver_type_not_the_required_type(
    db_session, monkeypatch
):
    # CompliIdentity declared the escalation needs a SERVICE approver; a
    # sufficient + human approver still fails the cross-check.
    _, _, decision = _escalated_decision(
        db_session, required_approver_types=["SERVICE"]
    )
    _patch_client(monkeypatch, _FakeAuthorityClient(_human_sufficient_ctx()))

    with pytest.raises(AuthorityVerificationError) as exc:
        escalation_approval_service.submit(
            db_session,
            ORG,
            decision_id=decision.id,
            approver_principal_id="principal-jordan",
            rationale="human, but not the required approver type",
        )
    assert exc.value.reason == "approver_type_mismatch"
    assert (
        escalation_approval_service.list_for_decision(db_session, ORG, decision.id)
        == []
    )


def test_submit_falls_back_to_layer1_when_no_required_type_declared(
    db_session, monkeypatch
):
    # required_approver_types empty (CompliIdentity named no approval
    # requirement for the action) -> the verify_approver_authority checks
    # stand on their own and a sufficient human approver is accepted.
    _, _, decision = _escalated_decision(db_session, required_approver_types=None)
    _patch_client(monkeypatch, _FakeAuthorityClient(_human_sufficient_ctx()))

    approval = escalation_approval_service.submit(
        db_session,
        ORG,
        decision_id=decision.id,
        approver_principal_id="principal-jordan",
        rationale="no required type declared; layer-1 checks suffice",
    )
    assert approval.status == EscalationApprovalStatus.ACTIVE.value
