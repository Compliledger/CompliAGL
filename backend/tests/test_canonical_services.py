"""Service and repository tests for canonical first-class resources."""

from __future__ import annotations

from app.repositories.canonical import (
    ActorIdentityRepository,
    IntentRepository,
)
from app.services.canonical import (
    actor_identity_service,
    governance_service,
    intent_service,
    operational_context_service,
    target_service,
)
from app.utils.canonical_enums import IntentStatus
from tests.canonical_factories import (
    ORG_A,
    actor_payload,
    authorization_payload,
    context_payload,
    decision_payload,
    evaluation_payload,
    execution_result_payload,
    intent_payload,
    target_payload,
)


# --------------------------------------------------------------------------- #
# Basic CRUD via services
# --------------------------------------------------------------------------- #
def test_create_and_get_actor_identity(db_session):
    actor = actor_identity_service.create(db_session, actor_payload())
    assert actor.id is not None
    assert actor.schema_version == 1
    assert actor.organization_id == ORG_A

    fetched = actor_identity_service.get(db_session, ORG_A, actor.id)
    assert fetched is not None
    assert fetched.id == actor.id
    assert fetched.credential_type == "DID"


def test_intent_stores_monetary_minor_units_not_float(db_session):
    intent = intent_service.create(db_session, intent_payload(amount_minor=25000))
    # Stored as an integer number of minor units — never a float.
    assert isinstance(intent.amount_minor, int)
    assert intent.amount_minor == 25000
    assert intent.amount_currency == "USD"
    assert intent.integrity_hash is not None
    assert intent.status == IntentStatus.SUBMITTED.value


def test_operational_context_computes_hash(db_session):
    ctx = operational_context_service.create(db_session, context_payload())
    assert ctx.context_hash is not None
    # Deterministic: identical state -> identical hash.
    ctx2 = operational_context_service.create(db_session, context_payload())
    assert ctx.context_hash == ctx2.context_hash


def test_repository_list_and_count_are_tenant_scoped(db_session):
    actor_identity_service.create(db_session, actor_payload(org="org-1"))
    actor_identity_service.create(db_session, actor_payload(org="org-1"))
    actor_identity_service.create(db_session, actor_payload(org="org-2"))

    repo = ActorIdentityRepository(db_session)
    assert repo.count("org-1") == 2
    assert repo.count("org-2") == 1
    assert len(repo.list("org-1")) == 2


# --------------------------------------------------------------------------- #
# The runtime can tie actor + intent + target + context into an evaluation
# --------------------------------------------------------------------------- #
def test_runtime_creates_and_retrieves_full_evaluation_chain(db_session):
    actor = actor_identity_service.create(db_session, actor_payload())
    intent = intent_service.create(db_session, intent_payload(actor_id=actor.id))
    target = target_service.create(db_session, target_payload())
    ctx = operational_context_service.create(db_session, context_payload())

    evaluation = governance_service.create_evaluation(
        db_session,
        evaluation_payload(ORG_A, actor.id, intent.id, target.id, ctx.id),
    )
    assert evaluation.actor_identity_id == actor.id
    assert evaluation.intent_id == intent.id
    assert evaluation.target_id == target.id
    assert evaluation.operational_context_id == ctx.id
    assert evaluation.evaluation_hash is not None

    # Retrieve it back tenant-scoped.
    reloaded = governance_service.get_evaluation(db_session, ORG_A, evaluation.id)
    assert reloaded is not None
    assert reloaded.id == evaluation.id

    # Decision -> Authorization -> ExternalExecutionResult chain.
    decision = governance_service.create_decision(
        db_session, decision_payload(ORG_A, evaluation.id, intent.id)
    )
    assert decision.outcome == "APPROVED"
    assert decision.decision_hash is not None

    authorization = governance_service.create_authorization(
        db_session, authorization_payload(ORG_A, decision.id, intent.id)
    )
    assert authorization.status == "AUTHORIZED"
    assert authorization.authorization_token is not None

    result = governance_service.create_execution_result(
        db_session, execution_result_payload(ORG_A, authorization.id, intent.id)
    )
    assert result.status == "CONFIRMED"
    assert result.external_reference == "x402-ref-1"


def test_create_evaluation_requires_existing_actor_and_intent(db_session):
    import pytest

    from app.services.canonical.errors import NotFoundError

    actor = actor_identity_service.create(db_session, actor_payload())
    with pytest.raises(NotFoundError):
        governance_service.create_evaluation(
            db_session,
            evaluation_payload(ORG_A, actor.id, "missing-intent"),
        )


def test_intent_repository_find_one_by_idempotency_key(db_session):
    intent = intent_service.create(
        db_session, intent_payload(idempotency_key="key-xyz")
    )
    found = IntentRepository(db_session).find_one(ORG_A, idempotency_key="key-xyz")
    assert found is not None
    assert found.id == intent.id
