"""Tests for the Circle Grant MVP seed functions and ENABLE_CIRCLE_MVP gating."""

from __future__ import annotations

from app.db import seed
from app.models.actor_identity import ActorIdentity
from app.models.organization import Organization
from app.services.canonical import governance_package_service


def test_seed_circle_treasury_agent_is_idempotent(db_session):
    seed.seed_organizations(db_session)
    seed.seed_circle_treasury_agent(db_session)
    seed.seed_circle_treasury_agent(db_session)

    actors = (
        db_session.query(ActorIdentity)
        .filter(ActorIdentity.id == seed.CIRCLE_TREASURY_AGENT_ID)
        .all()
    )
    assert len(actors) == 1
    actor = actors[0]
    assert actor.verification_status == "VERIFIED"
    assert actor.revocation_status == "ACTIVE"


def test_seed_circle_package_is_idempotent(db_session):
    seed.seed_organizations(db_session)
    seed.seed_circle_package(db_session)
    seed.seed_circle_package(db_session)

    from app.db.circle_treasury_package import PACKAGE_NAME, PACKAGE_VERSION

    published = governance_package_service.get_published_version(
        db_session, seed.CIRCLE_ORG_ID, PACKAGE_NAME, PACKAGE_VERSION
    )
    assert published is not None


def test_seed_demo_data_skips_circle_seeds_when_flag_unset(db_session, monkeypatch):
    monkeypatch.delenv("ENABLE_CIRCLE_MVP", raising=False)
    seed.seed_demo_data(db_session)

    assert db_session.get(Organization, seed.CIRCLE_ORG_ID) is None
    assert db_session.get(ActorIdentity, seed.CIRCLE_TREASURY_AGENT_ID) is None


def test_seed_demo_data_runs_circle_seeds_when_flag_true(db_session, monkeypatch):
    monkeypatch.setenv("ENABLE_CIRCLE_MVP", "true")
    seed.seed_demo_data(db_session)

    assert db_session.get(Organization, seed.CIRCLE_ORG_ID) is not None
    assert db_session.get(ActorIdentity, seed.CIRCLE_TREASURY_AGENT_ID) is not None


def test_circle_seed_only_touches_its_own_org(db_session, monkeypatch):
    monkeypatch.setenv("ENABLE_CIRCLE_MVP", "true")
    seed.seed_demo_data(db_session)

    # HarborStone's actors/org are unaffected by the Circle seed running.
    harborstone_actor = db_session.get(ActorIdentity, seed.HARBORSTONE_AIRA_ACTOR_ID)
    assert harborstone_actor is not None
    assert harborstone_actor.organization_id == seed.HARBORSTONE_ORG_ID

    circle_actor = db_session.get(ActorIdentity, seed.CIRCLE_TREASURY_AGENT_ID)
    assert circle_actor.organization_id == seed.CIRCLE_ORG_ID
