"""Payload factories shared across canonical service/repository tests."""

from __future__ import annotations

from app.schemas.canonical.actor_identity import ActorIdentityCreate
from app.schemas.canonical.governance import (
    DecisionCreate,
    ExecutionAuthorizationCreate,
    ExternalExecutionResultCreate,
    GovernanceEvaluationCreate,
)
from app.schemas.canonical.intent import IntentCreate
from app.schemas.canonical.operational_context import OperationalContextCreate
from app.schemas.canonical.target import TargetCreate
from app.utils.canonical_enums import (
    CanonicalActorType,
    CredentialType,
    DecisionOutcome,
    IntentType,
    TargetType,
)

ORG_A = "org-alpha"
ORG_B = "org-beta"


def actor_payload(org: str = ORG_A, **overrides) -> ActorIdentityCreate:
    data = dict(
        organization_id=org,
        actor_type=CanonicalActorType.AI_AGENT,
        external_account_id="ext-123",
        credential_type=CredentialType.DID,
        credential_issuer="did:example:issuer",
        credential_reference="did:example:actor#key-1",
        identity_metadata={"team": "payments"},
    )
    data.update(overrides)
    return ActorIdentityCreate(**data)


def intent_payload(org: str = ORG_A, actor_id: str = "actor-1", **overrides) -> IntentCreate:
    data = dict(
        organization_id=org,
        intent_type=IntentType.PAYMENT,
        action="book_flight",
        requested_outcome="ticket_issued",
        actor_id=actor_id,
        originating_application="travel-app",
        parameters={"route": "SFO-JFK"},
        amount_minor=25000,
        amount_currency="USD",
    )
    data.update(overrides)
    return IntentCreate(**data)


def target_payload(org: str = ORG_A, **overrides) -> TargetCreate:
    data = dict(
        organization_id=org,
        target_type=TargetType.MERCHANT,
        external_identifier="merchant-airline-01",
        owner="Airline Inc",
        target_metadata={"category": "airline"},
    )
    data.update(overrides)
    return TargetCreate(**data)


def context_payload(org: str = ORG_A, **overrides) -> OperationalContextCreate:
    data = dict(
        organization_id=org,
        business_unit="travel",
        jurisdiction="US",
        risk_state={"score": 12},
        allowance_state={"remaining_minor": 500000, "currency": "USD"},
        network_state={"chain": "base"},
    )
    data.update(overrides)
    return OperationalContextCreate(**data)


def evaluation_payload(
    org: str, actor_identity_id: str, intent_id: str, target_id=None, context_id=None
) -> GovernanceEvaluationCreate:
    return GovernanceEvaluationCreate(
        organization_id=org,
        actor_identity_id=actor_identity_id,
        intent_id=intent_id,
        target_id=target_id,
        operational_context_id=context_id,
    )


def decision_payload(org: str, evaluation_id: str, intent_id: str) -> DecisionCreate:
    return DecisionCreate(
        organization_id=org,
        governance_evaluation_id=evaluation_id,
        intent_id=intent_id,
        outcome=DecisionOutcome.APPROVED,
        reason_codes=["APPROVED_BY_POLICY"],
        policy_version="v1",
    )


def authorization_payload(
    org: str, decision_id: str, intent_id: str
) -> ExecutionAuthorizationCreate:
    return ExecutionAuthorizationCreate(
        organization_id=org,
        decision_id=decision_id,
        intent_id=intent_id,
        constraints={"max_amount_minor": 30000},
    )


def execution_result_payload(
    org: str, authorization_id: str, intent_id: str
) -> ExternalExecutionResultCreate:
    from app.utils.canonical_enums import ExecutionResultStatus

    return ExternalExecutionResultCreate(
        organization_id=org,
        execution_authorization_id=authorization_id,
        intent_id=intent_id,
        adapter="x402",
        status=ExecutionResultStatus.CONFIRMED,
        external_reference="x402-ref-1",
        settlement_chain="base",
        result_payload={"tx_hash": "0xabc"},
    )
