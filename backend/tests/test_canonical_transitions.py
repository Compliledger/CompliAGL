"""Invalid lifecycle transition tests."""

from __future__ import annotations

import pytest

from app.services.canonical import governance_service, intent_service
from app.services.canonical.errors import InvalidTransitionError
from app.utils.canonical_enums import AuthorizationStatus, IntentStatus
from tests.canonical_factories import (
    ORG_A,
    actor_payload,
    authorization_payload,
    decision_payload,
    evaluation_payload,
    intent_payload,
)
from app.services.canonical import actor_identity_service


# --------------------------------------------------------------------------- #
# Intent lifecycle
# --------------------------------------------------------------------------- #
def test_intent_valid_transition_chain(db_session):
    intent = intent_service.create(db_session, intent_payload())
    assert intent.status == IntentStatus.SUBMITTED.value
    intent = intent_service.transition_status(
        db_session, ORG_A, intent.id, IntentStatus.EVALUATED
    )
    assert intent.status == IntentStatus.EVALUATED.value
    intent = intent_service.transition_status(
        db_session, ORG_A, intent.id, IntentStatus.AUTHORIZED
    )
    assert intent.status == IntentStatus.AUTHORIZED.value
    intent = intent_service.transition_status(
        db_session, ORG_A, intent.id, IntentStatus.EXECUTED
    )
    assert intent.status == IntentStatus.EXECUTED.value


def test_intent_invalid_transition_from_submitted_to_executed(db_session):
    intent = intent_service.create(db_session, intent_payload())
    with pytest.raises(InvalidTransitionError):
        intent_service.transition_status(
            db_session, ORG_A, intent.id, IntentStatus.EXECUTED
        )


def test_intent_invalid_transition_from_terminal_state(db_session):
    intent = intent_service.create(db_session, intent_payload())
    intent_service.transition_status(db_session, ORG_A, intent.id, IntentStatus.DENIED)
    with pytest.raises(InvalidTransitionError):
        intent_service.transition_status(
            db_session, ORG_A, intent.id, IntentStatus.EVALUATED
        )


def test_intent_no_op_transition_is_rejected(db_session):
    intent = intent_service.create(db_session, intent_payload())
    with pytest.raises(InvalidTransitionError):
        intent_service.transition_status(
            db_session, ORG_A, intent.id, IntentStatus.SUBMITTED
        )


# --------------------------------------------------------------------------- #
# ExecutionAuthorization lifecycle
# --------------------------------------------------------------------------- #
def _make_authorization(db_session):
    actor = actor_identity_service.create(db_session, actor_payload())
    intent = intent_service.create(db_session, intent_payload(actor_id=actor.id))
    evaluation = governance_service.create_evaluation(
        db_session, evaluation_payload(ORG_A, actor.id, intent.id)
    )
    decision = governance_service.create_decision(
        db_session, decision_payload(ORG_A, evaluation.id, intent.id)
    )
    return governance_service.create_authorization(
        db_session, authorization_payload(ORG_A, decision.id, intent.id)
    )


def test_authorization_valid_transition_to_consumed(db_session):
    auth = _make_authorization(db_session)
    assert auth.status == AuthorizationStatus.AUTHORIZED.value
    auth = governance_service.transition_authorization(
        db_session, ORG_A, auth.id, AuthorizationStatus.CONSUMED
    )
    assert auth.status == AuthorizationStatus.CONSUMED.value


def test_authorization_invalid_transition_after_consumed(db_session):
    auth = _make_authorization(db_session)
    governance_service.transition_authorization(
        db_session, ORG_A, auth.id, AuthorizationStatus.CONSUMED
    )
    with pytest.raises(InvalidTransitionError):
        governance_service.transition_authorization(
            db_session, ORG_A, auth.id, AuthorizationStatus.AUTHORIZED
        )


def test_api_invalid_intent_transition_returns_409(api_client):
    created = api_client.post(
        "/api/v1/intents",
        json={
            "organization_id": ORG_A,
            "intent_type": "PAYMENT",
            "action": "pay",
            "actor_id": "actor-1",
            "amount_minor": 100,
            "amount_currency": "USD",
        },
    )
    assert created.status_code == 201
    intent_id = created.json()["id"]
    resp = api_client.post(
        f"/api/v1/intents/{intent_id}/transition",
        json={"status": "EXECUTED"},
        headers={"X-Organization-Id": ORG_A},
    )
    assert resp.status_code == 409
