"""Tests for the HarborStone Demo #3 actor-identity seed.

The three actors carry their CompliIdentity ``principal_id`` in the field
``decision_service._authority_principal_id`` reads (``human_principal_id``
for the HUMAN, ``wallet_or_agent_account_id`` for the AI_AGENTs), mirrored
into ``identity_metadata``. The seed must be idempotent and must refresh the
principal ids in place (not duplicate rows) when the local CompliIdentity
instance is regenerated.
"""

from __future__ import annotations

import json

import app.db.seed as seed
from app.db.seed import (
    HARBORSTONE_AIRA_ACTOR_ID,
    HARBORSTONE_JORDAN_ACTOR_ID,
    HARBORSTONE_ORG_ID,
    HARBORSTONE_SENTRY_ACTOR_ID,
    seed_harborstone_actors,
    seed_organizations,
)
from app.models.actor_identity import ActorIdentity
from app.services.canonical import decision_service
from app.utils.canonical_enums import CanonicalActorType


def _by_id(db):
    return {a.id: a for a in db.query(ActorIdentity).all()}


def test_seed_creates_three_actors_with_principal_ids(db_session):
    seed_organizations(db_session)
    seed_harborstone_actors(db_session)

    actors = _by_id(db_session)
    assert set(actors) == {
        HARBORSTONE_AIRA_ACTOR_ID,
        HARBORSTONE_SENTRY_ACTOR_ID,
        HARBORSTONE_JORDAN_ACTOR_ID,
    }
    for a in actors.values():
        assert a.organization_id == HARBORSTONE_ORG_ID

    aira = actors[HARBORSTONE_AIRA_ACTOR_ID]
    sentry = actors[HARBORSTONE_SENTRY_ACTOR_ID]
    jordan = actors[HARBORSTONE_JORDAN_ACTOR_ID]

    # AI_AGENT -> wallet_or_agent_account_id; HUMAN -> human_principal_id
    assert aira.actor_type == CanonicalActorType.AI_AGENT.value
    assert aira.wallet_or_agent_account_id == seed._HARBORSTONE_AIRA_PRINCIPAL_ID
    assert aira.human_principal_id is None

    assert sentry.wallet_or_agent_account_id == seed._HARBORSTONE_SENTRY_PRINCIPAL_ID

    assert jordan.actor_type == CanonicalActorType.HUMAN.value
    assert jordan.human_principal_id == seed._HARBORSTONE_JORDAN_PRINCIPAL_ID
    assert jordan.wallet_or_agent_account_id is None


def test_principal_id_mirrored_into_metadata(db_session):
    seed_organizations(db_session)
    seed_harborstone_actors(db_session)
    jordan = db_session.get(ActorIdentity, HARBORSTONE_JORDAN_ACTOR_ID)
    md = json.loads(jordan.identity_metadata)
    assert md["compliidentity_principal_id"] == seed._HARBORSTONE_JORDAN_PRINCIPAL_ID
    assert md["compliidentity_tenant_id"] == HARBORSTONE_ORG_ID
    assert md["compliidentity_instance"] == seed._COMPLIIDENTITY_INSTANCE


def test_authority_principal_id_mapping_resolves(db_session):
    """The seeded fields are exactly what the decision engine probes with."""
    seed_organizations(db_session)
    seed_harborstone_actors(db_session)
    aira = db_session.get(ActorIdentity, HARBORSTONE_AIRA_ACTOR_ID)
    jordan = db_session.get(ActorIdentity, HARBORSTONE_JORDAN_ACTOR_ID)
    assert (
        decision_service._authority_principal_id(aira)
        == seed._HARBORSTONE_AIRA_PRINCIPAL_ID
    )
    assert (
        decision_service._authority_principal_id(jordan)
        == seed._HARBORSTONE_JORDAN_PRINCIPAL_ID
    )


def test_seed_is_idempotent(db_session):
    seed_organizations(db_session)
    seed_harborstone_actors(db_session)
    seed_harborstone_actors(db_session)
    seed_harborstone_actors(db_session)
    assert db_session.query(ActorIdentity).count() == 3


def test_reseed_refreshes_principal_id_in_place(db_session, monkeypatch):
    """Regenerating the CompliIdentity instance re-issues principal ids; the
    seed updates the existing rows rather than inserting duplicates."""
    seed_organizations(db_session)
    seed_harborstone_actors(db_session)

    monkeypatch.setattr(seed, "_HARBORSTONE_AIRA_PRINCIPAL_ID", "refreshed-aira-pid")
    monkeypatch.setattr(seed, "_COMPLIIDENTITY_INSTANCE", "regenerated.db")
    seed_harborstone_actors(db_session)

    assert db_session.query(ActorIdentity).count() == 3
    aira = db_session.get(ActorIdentity, HARBORSTONE_AIRA_ACTOR_ID)
    assert aira.wallet_or_agent_account_id == "refreshed-aira-pid"
    md = json.loads(aira.identity_metadata)
    assert md["compliidentity_principal_id"] == "refreshed-aira-pid"
    assert md["compliidentity_instance"] == "regenerated.db"
