"""Persistent demo seed data.

Seeds the **database** (not an in-memory registry) with a canonical demo actor
and policy so the Compli402 governance flow works out of the box. Seeding is
idempotent and, because it is persisted, survives application restarts.

This replaces the deprecated in-memory ``seed_demo_actors`` /
``seed_demo_policies`` helpers.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.policy import Policy
from app.mvp2.schemas.actor import ActorType
from app.services import actor_registry

# Canonical, stable demo identifiers (kept identical to the historical demo
# ids so existing clients and docs continue to work).
DEMO_TRAVEL_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEMO_OPS_MANAGER_ID = UUID("00000000-0000-0000-0000-000000000002")
DEMO_TRAVEL_POLICY_ID = UUID("00000000-0000-0000-0000-000000000101")


def seed_demo_actors(db: Session) -> None:
    """Idempotently persist the canonical demo actors."""
    actor_registry.upsert_actor(
        db,
        actor_id=DEMO_TRAVEL_AGENT_ID,
        name="TravelAgent-01",
        actor_type=ActorType.AGENT,
        wallet_address="agent_wallet_travel_001",
    )
    actor_registry.upsert_actor(
        db,
        actor_id=DEMO_OPS_MANAGER_ID,
        name="OpsManager-01",
        actor_type=ActorType.HUMAN,
        wallet_address="human_wallet_ops_001",
    )


def seed_demo_policies(db: Session) -> None:
    """Idempotently persist the canonical demo policy.

    Encodes the same governance semantics as the historical demo policy:
    ``max per-transaction 500``, ``escalate above 250``, ``deny BTC``.
    """
    policy = db.get(Policy, str(DEMO_TRAVEL_POLICY_ID))
    if policy is None:
        policy = Policy(id=str(DEMO_TRAVEL_POLICY_ID))
        db.add(policy)
    policy.agent_id = str(DEMO_TRAVEL_AGENT_ID)
    policy.policy_name = "Travel Spend Policy"
    policy.description = "Governs travel-related agent spending."
    policy.policy_type = "spend"
    policy.status = "ACTIVE"
    policy.is_active = True
    policy.per_tx_limit = 500.0
    policy.escalation_threshold = 250.0
    policy.require_approval_above_threshold = True
    policy.blocked_asset_symbols = json.dumps(["BTC"])
    db.commit()


def seed_organizations(db: Session) -> None:
    """Idempotently persist the known, real organizations.

    ``organization_id`` is validated against this table on every canonical
    read/write (see ``app.services.canonical.organization_service``), so the
    tenants already in use must exist here. This runs on every boot — the
    same idempotent pattern as the rest of this module — because Alembic
    migrations are not invoked as part of deployment (see Procfile).
    """
    for organization_id, organization_name in (
        ("default-org", "Default Organization"),
        ("securerob-pilot", "SecureRob Pilot"),
        ("harborstone-demo", "HarborStone Demo"),
    ):
        org = db.get(Organization, organization_id)
        if org is None:
            db.add(
                Organization(
                    organization_id=organization_id,
                    organization_name=organization_name,
                    status="ACTIVE",
                )
            )
    db.commit()


def seed_demo_data(db: Session) -> None:
    """Seed all canonical demo data (organizations + actors + policies)."""
    seed_organizations(db)
    seed_demo_actors(db)
    seed_demo_policies(db)
