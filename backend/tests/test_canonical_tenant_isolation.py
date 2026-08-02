"""Tenant isolation tests — every query is scoped by organization_id."""

from __future__ import annotations

import pytest

from app.repositories.canonical import ActorIdentityRepository
from app.services.canonical import actor_identity_service, intent_service
from tests.canonical_factories import ORG_A, ORG_B, actor_payload, intent_payload


def test_cross_tenant_get_returns_none(db_session):
    actor = actor_identity_service.create(db_session, actor_payload(org=ORG_A))
    # Same id, wrong tenant -> not visible.
    assert actor_identity_service.get(db_session, ORG_B, actor.id) is None
    # Correct tenant -> visible.
    assert actor_identity_service.get(db_session, ORG_A, actor.id) is not None


def test_cross_tenant_list_excludes_other_org(db_session):
    intent_service.create(db_session, intent_payload(org=ORG_A))
    intent_service.create(db_session, intent_payload(org=ORG_B))
    a_items = intent_service.list_(db_session, ORG_A)
    b_items = intent_service.list_(db_session, ORG_B)
    assert all(i.organization_id == ORG_A for i in a_items)
    assert all(i.organization_id == ORG_B for i in b_items)
    assert len(a_items) == 1 and len(b_items) == 1


def test_repository_rejects_missing_tenant(db_session):
    with pytest.raises(ValueError):
        ActorIdentityRepository(db_session).get("", "some-id")


def test_api_cross_tenant_access_is_404(api_client):
    created = api_client.post(
        "/api/v1/actor-identities",
        json={"organization_id": ORG_A, "actor_type": "AI_AGENT"},
    )
    assert created.status_code == 201
    actor_id = created.json()["id"]

    # Wrong tenant header -> 404.
    wrong = api_client.get(
        f"/api/v1/actor-identities/{actor_id}",
        headers={"X-Organization-Id": ORG_B},
    )
    assert wrong.status_code == 404

    # Correct tenant header -> 200.
    right = api_client.get(
        f"/api/v1/actor-identities/{actor_id}",
        headers={"X-Organization-Id": ORG_A},
    )
    assert right.status_code == 200


def test_api_requires_tenant_for_reads(api_client):
    resp = api_client.get("/api/v1/actor-identities")
    assert resp.status_code == 400
