"""End-to-end Demo #3 orchestration: the full governed-action chain from
AIRA's initial propose through Jordan's human approval, execution
authorization issue/verify/consume, and AIProof generation -- confirmed
against the derived run-state view (``demo_run_service``) at every stage,
then against a full ``demo_reset_service`` reset.

In-process, real service/DB calls throughout the whole chain; the only
mocked boundary is the CompliIdentity HTTP client
(``authority_context_service.default_client``), the same convention every
other test in this suite already uses (``test_governed_action_service.py``,
``test_escalation_approval.py``). The fake client discriminates by
``action`` so the escalating actor's ``propose`` probe and the approver's
``approve`` probe can return different, realistic answers from one fixture
-- exactly how the real CompliIdentity endpoint behaves for two different
principals/actions against the same resource.
"""

from __future__ import annotations

import json

import pytest

from app.db import seed
from app.db.harborstone_package import build_harborstone_package
from app.schemas.canonical.aiproof import (
    ActorIdentityRef,
    DecisionRef,
    ExecutionAuthorizationRef,
    ExternalExecutionResultRef,
    GovernedOutcome,
    IntentRef,
    ProofMetadata,
    ProofTimestamps,
)
from app.schemas.canonical.governance import ExternalExecutionResultCreate
from app.services.canonical import (
    authority_context_service,
    authorization_service,
    escalation_approval_service,
    governance_package_service,
    governance_service,
    governed_action_service,
)
from app.services.canonical import demo_reset_service, demo_run_service
from app.services.canonical.aiproof import generator
from app.services.canonical.aiproof import service as aiproof_service
from app.services.canonical.aiproof.verify import verify_aiproof
from app.services.canonical.authority_context_service import AuthorityContext
from app.services.canonical.errors import ConflictError
from app.services.evidence.connectors import ConnectorRegistry
from app.services.evidence.connectors.harborstone_sentry_screening import (
    harborstone_sentry_screening_connector,
)
from app.utils.canonical_enums import (
    AuthorizationStatus,
    DecisionOutcome,
    EscalationApprovalStatus,
    ExecutionResultStatus,
    IntentType,
)
from app.utils.timestamps import utc_now

ORG = "harborstone-demo"
CASE = "HARBORSTONE-2024-0042"
_AT_THRESHOLD = 25_000_000
_APPROVER = "jordan-principal-id"
_CORRELATION_ID = "corr-full-chain-1"


@pytest.fixture()
def published_package(db_session):
    seed.seed_organizations(db_session)
    seed.seed_harborstone_actors(db_session)
    pkg = governance_package_service.create(db_session, build_harborstone_package(ORG))
    result = governance_package_service.validate(db_session, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(
        db_session, ORG, pkg.id,
        approver_principal_id="tester", rationale="approved for test",
    )
    governance_package_service.publish(db_session, ORG, pkg.id)
    return pkg


class _DualActionClient:
    """Fake CompliIdentity client that answers differently per ``action``.

    AIRA's escalating ``propose`` probe and Jordan's ``approve`` probe are
    two different principals asking two different questions about the same
    resource -- a single fixed context (the pattern every other test in this
    suite uses) can't represent both at once for a real end-to-end chain.
    """

    def __init__(self, *, propose_ctx: AuthorityContext, approve_ctx: AuthorityContext):
        self._propose_ctx = propose_ctx
        self._approve_ctx = approve_ctx
        self.calls: list[dict] = []

    def fetch(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("action") == "approve":
            return self._approve_ctx
        return self._propose_ctx


@pytest.fixture()
def dual_authority(monkeypatch):
    propose_ctx = AuthorityContext(
        status="OK",
        sufficient=False,
        permission_present=True,
        approval_required=True,
        findings=("approval_required",),
    )
    approve_ctx = AuthorityContext(
        status="OK",
        sufficient=True,
        permission_present=True,
        approval_required=False,
        findings=("permission_present",),
        raw={
            "principal_type": "HUMAN",
            "principal": {"principal_type": "HUMAN", "status": "ACTIVE"},
            "authority_for_request": {"sufficient": True, "applicable_approvals": []},
        },
    )
    client = _DualActionClient(propose_ctx=propose_ctx, approve_ctx=approve_ctx)
    monkeypatch.setattr(
        authority_context_service, "default_client", lambda **kw: client
    )
    return client


def _view(db):
    return demo_run_service.get_run_state(db, ORG, correlation_id=_CORRELATION_ID)


def test_full_governed_action_chain_and_reset(db_session, published_package, dual_authority):
    # --- Nothing started yet: no run for this correlation id. --------------
    assert _view(db_session) is None

    # --- 1. AIRA proposes an over-threshold transfer -> ESCALATED. ---------
    result = governed_action_service.propose(
        db_session,
        ORG,
        actor_id=seed.HARBORSTONE_AIRA_ACTOR_ID,
        intent_type=IntentType.TRANSFER,
        action="astra_transfer",
        compliidentity_resource="aml.action",
        compliidentity_action="propose",
        resource_instance=CASE,
        target_identifier="wallet_001",
        rationale="review complete",
        amount_minor=_AT_THRESHOLD,
        amount_currency="USD",
        correlation_id=_CORRELATION_ID,
        registry=ConnectorRegistry([harborstone_sentry_screening_connector()]),
    )
    assert result.decision.outcome == DecisionOutcome.ESCALATED.value
    assert "HUMAN_APPROVAL_REQUIRED" in json.loads(result.decision.reason_codes)

    view = _view(db_session)
    assert view["stage"] == demo_run_service.STAGE_AWAITING_APPROVAL
    assert view["case_id"] == CASE
    assert view["decision"]["outcome"] == "ESCALATED"
    assert view["escalation_approval"] is None
    assert view["execution_authorization"] is None
    assert view["aiproof"] is None

    # --- 2. Jordan submits an authority-verified approval. ------------------
    approval = escalation_approval_service.submit(
        db_session,
        ORG,
        decision_id=result.decision.id,
        approver_principal_id=_APPROVER,
        rationale="reviewed and approved",
    )
    assert approval.status == EscalationApprovalStatus.ACTIVE.value

    view = _view(db_session)
    assert view["stage"] == demo_run_service.STAGE_APPROVAL_SUBMITTED
    assert view["escalation_approval"]["status"] == "ACTIVE"
    assert view["escalation_approval"]["escalation_approval_id"] == (
        approval.escalation_approval_id
    )

    # --- 3. apply() re-decides, consuming the approval -> APPROVED. --------
    new_decision = escalation_approval_service.apply(
        db_session, ORG, escalation_approval_id=approval.id
    )
    assert new_decision.outcome == DecisionOutcome.APPROVED.value
    assert new_decision.prior_decision_id == result.decision.id
    assert "HARBORSTONE_APPROVED_VIA_HUMAN" in json.loads(new_decision.reason_codes)

    db_session.refresh(approval)
    assert approval.status == EscalationApprovalStatus.CONSUMED.value

    view = _view(db_session)
    assert view["stage"] == demo_run_service.STAGE_APPROVED
    assert view["decision"]["decision_id"] == new_decision.id
    assert view["decision"]["prior_decision_id"] == result.decision.id
    assert view["escalation_approval"]["status"] == "CONSUMED"

    # --- 4. Issue a signed execution authorization for the APPROVED decision.
    auth = authorization_service.issue(
        db_session, ORG, new_decision.id, permitted_execution_system="hedera-testnet"
    )
    assert auth.status == AuthorizationStatus.ISSUED.value

    view = _view(db_session)
    assert view["stage"] == demo_run_service.STAGE_EXECUTION_AUTHORIZED
    assert view["execution_authorization"]["status"] == "ISSUED"

    # --- 5. The executing system verifies it before acting on it. ----------
    verify_result = authorization_service.verify(db_session, ORG, auth.id)
    assert verify_result["valid"] is True, verify_result["reasons"]
    db_session.refresh(auth)
    assert auth.status == AuthorizationStatus.ACTIVE.value

    view = _view(db_session)
    assert view["stage"] == demo_run_service.STAGE_ACTION_INTEGRITY_VERIFIED
    assert view["execution_authorization"]["status"] == "ACTIVE"

    # --- 6. The Gateway reports the completed external execution. ----------
    execution_result = governance_service.create_execution_result(
        db_session,
        ExternalExecutionResultCreate(
            organization_id=ORG,
            execution_authorization_id=auth.id,
            intent_id=result.intent.id,
            adapter="hedera",
            status=ExecutionResultStatus.CONFIRMED,
            external_reference="0.0.123456@1700000000.000000000",
            settlement_chain="hedera-testnet",
        ),
    )

    # --- 7. The one-time-use authorization is consumed (replay-protected). -
    consumed_auth = authorization_service.consume(db_session, ORG, auth.id)
    assert consumed_auth.status == AuthorizationStatus.CONSUMED.value
    with pytest.raises(ConflictError):
        authorization_service.consume(db_session, ORG, auth.id)

    view = _view(db_session)
    assert view["stage"] == demo_run_service.STAGE_EXECUTED
    assert view["execution_result"]["status"] == "CONFIRMED"
    assert view["execution_result"]["adapter"] == "hedera"

    # --- 8. Generate + sign the canonical AIProof for this governed outcome.
    proof_content = dict(
        metadata=ProofMetadata(
            aiproof_id=f"proof-{result.intent.id}",
            organization_id=ORG,
            governance_evaluation_id=result.policy_resolution.id,
            correlation_id=_CORRELATION_ID,
            governed_outcome=GovernedOutcome.APPROVED_AND_EXECUTED,
        ),
        actor_identity=ActorIdentityRef(
            actor_identity_id=seed.HARBORSTONE_AIRA_ACTOR_ID,
        ),
        intent=IntentRef(
            intent_id=result.intent.id,
            intent_type=result.intent.intent_type,
            action=result.intent.action,
            amount_minor=result.intent.amount_minor,
            amount_currency=result.intent.amount_currency,
        ),
        decision=DecisionRef(
            decision_id=new_decision.id,
            outcome=new_decision.outcome,
            reason_codes=json.loads(new_decision.reason_codes),
            supersession_status=new_decision.supersession_status,
            prior_decision_id=new_decision.prior_decision_id,
            decision_hash=new_decision.decision_hash,
        ),
        execution_authorization=ExecutionAuthorizationRef(
            execution_authorization_id=auth.id,
            status=consumed_auth.status,
            authorized_action=auth.authorized_action,
            authorization_hash=auth.authorization_hash,
        ),
        external_execution_result=ExternalExecutionResultRef(
            external_execution_result_id=execution_result.id,
            adapter=execution_result.adapter,
            status=execution_result.status,
            external_reference=execution_result.external_reference,
            settlement_chain=execution_result.settlement_chain,
        ),
        timestamps=ProofTimestamps(
            generated_at=utc_now().isoformat(),
            decided_at=new_decision.decided_at.isoformat(),
            authorized_at=auth.authorized_at.isoformat(),
            executed_at=execution_result.executed_at.isoformat(),
        ),
    )
    proof = generator.generate_signed_aiproof(**proof_content)
    row = aiproof_service.store_aiproof(db_session, proof)

    view = _view(db_session)
    assert view["stage"] == demo_run_service.STAGE_PROOF_GENERATED
    assert view["aiproof"]["aiproof_id"] == row.id
    assert view["aiproof"]["governed_outcome"] == GovernedOutcome.APPROVED_AND_EXECUTED.value

    # The proof round-trips through independent local verification exactly
    # like a downstream relying party (CompliLedger) would check it.
    verification = verify_aiproof(proof)
    assert verification.valid, verification.errors

    # list_run_states finds the same run when queried by case id.
    runs = demo_run_service.list_run_states(db_session, ORG, case_id=CASE)
    assert len(runs) == 1
    assert runs[0]["correlation_id"] == _CORRELATION_ID
    assert runs[0]["stage"] == demo_run_service.STAGE_PROOF_GENERATED

    # --- 9. Reset clears every per-run record but leaves infrastructure. ---
    deleted = demo_reset_service.reset_demo_state(db_session, ORG)
    assert deleted["intents"] == 1
    assert deleted["decisions"] == 2  # the superseded ESCALATED + the APPROVED
    assert deleted["escalation_approvals"] == 1
    assert deleted["execution_authorizations"] == 1
    assert deleted["external_execution_results"] == 1
    assert deleted["canonical_ai_proofs"] == 1

    assert _view(db_session) is None
    assert demo_run_service.list_run_states(db_session, ORG, case_id=CASE) == []

    # Seeded infrastructure survives the reset.
    from app.repositories.canonical import (
        ActorIdentityRepository,
        ExecutableGovernancePackageRepository,
    )

    assert ActorIdentityRepository(db_session).get(
        ORG, seed.HARBORSTONE_AIRA_ACTOR_ID
    ) is not None
    assert ExecutableGovernancePackageRepository(db_session).get(
        ORG, published_package.id
    ) is not None

    # A fresh run through the same case works cleanly after reset.
    second = governed_action_service.propose(
        db_session,
        ORG,
        actor_id=seed.HARBORSTONE_AIRA_ACTOR_ID,
        intent_type=IntentType.TRANSFER,
        action="astra_transfer",
        compliidentity_resource="aml.action",
        compliidentity_action="propose",
        resource_instance=CASE,
        target_identifier="wallet_001",
        rationale="review complete",
        amount_minor=_AT_THRESHOLD,
        amount_currency="USD",
        correlation_id=_CORRELATION_ID,
        registry=ConnectorRegistry([harborstone_sentry_screening_connector()]),
    )
    assert second.decision.outcome == DecisionOutcome.ESCALATED.value
    assert _view(db_session)["stage"] == demo_run_service.STAGE_AWAITING_APPROVAL
