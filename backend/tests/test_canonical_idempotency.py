"""Idempotency tests for intent creation."""

from __future__ import annotations

from app.services.canonical import intent_service
from tests.canonical_factories import ORG_A, ORG_B, intent_payload


def test_same_idempotency_key_returns_same_intent(db_session):
    first = intent_service.create(
        db_session, intent_payload(idempotency_key="dup-key")
    )
    second = intent_service.create(
        db_session, intent_payload(idempotency_key="dup-key", action="different")
    )
    # Same id — no duplicate created, original preserved.
    assert first.id == second.id
    assert second.action == "book_flight"
    assert intent_service.list_(db_session, ORG_A).__len__() == 1


def test_idempotency_key_is_scoped_per_tenant(db_session):
    a = intent_service.create(
        db_session, intent_payload(org=ORG_A, idempotency_key="shared")
    )
    b = intent_service.create(
        db_session, intent_payload(org=ORG_B, idempotency_key="shared")
    )
    # Same key in different tenants -> distinct intents.
    assert a.id != b.id


def test_missing_idempotency_key_always_creates_new(db_session):
    a = intent_service.create(db_session, intent_payload())
    b = intent_service.create(db_session, intent_payload())
    assert a.id != b.id


def test_api_idempotent_intent_creation(api_client):
    body = {
        "organization_id": ORG_A,
        "intent_type": "PAYMENT",
        "action": "pay",
        "actor_id": "actor-1",
        "amount_minor": 500,
        "amount_currency": "USD",
        "idempotency_key": "api-dup",
    }
    first = api_client.post("/api/v1/intents", json=body)
    second = api_client.post("/api/v1/intents", json={**body, "action": "changed"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    # Original action preserved (idempotent replay, not overwrite).
    assert second.json()["action"] == "pay"
