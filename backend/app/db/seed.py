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

from app.models.actor_identity import ActorIdentity
from app.models.organization import Organization
from app.models.policy import Policy
from app.mvp2.schemas.actor import ActorType
from app.services import actor_registry
from app.utils.canonical_enums import (
    CanonicalActorType,
    CredentialType,
    RevocationStatus,
    VerificationStatus,
)

# Canonical, stable demo identifiers (kept identical to the historical demo
# ids so existing clients and docs continue to work).
DEMO_TRAVEL_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEMO_OPS_MANAGER_ID = UUID("00000000-0000-0000-0000-000000000002")
DEMO_TRAVEL_POLICY_ID = UUID("00000000-0000-0000-0000-000000000101")

# --- HarborStone Demo #3 (CompliIdentity integration) --------------------- #
# Stable CompliAGL-side ActorIdentity ids for the three HarborStone actors.
# These never change; the CompliIdentity ``principal_id`` each one carries
# (below) is instance-specific and refreshed *in place* on the same three
# rows whenever the local CompliIdentity working DB is regenerated.
HARBORSTONE_ORG_ID = "harborstone-demo"
HARBORSTONE_AIRA_ACTOR_ID = "harborstone-demo-actor-aira"
HARBORSTONE_SENTRY_ACTOR_ID = "harborstone-demo-actor-sentry"
HARBORSTONE_JORDAN_ACTOR_ID = "harborstone-demo-actor-jordan"

# CompliIdentity principal ids — issued by the local ``compliidentity_demo3_
# step2.db`` instance (see ``demo3_step2/compliidentity_setup_phases_1_7.py``
# and its ``compliidentity_setup_results.json``). Regenerating that instance
# re-issues these; update the three values here when that happens.
_COMPLIIDENTITY_INSTANCE = "compliidentity_demo3_step2.db"
_HARBORSTONE_AIRA_PRINCIPAL_ID = "e35ac15a-b8f4-4a7d-9003-5a0d15750ade"
_HARBORSTONE_SENTRY_PRINCIPAL_ID = "302415c0-00ab-49b0-8a65-01175c0deb68"
_HARBORSTONE_JORDAN_PRINCIPAL_ID = "e35d7b95-1a10-4654-9b02-2181df052f96"


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


def seed_harborstone_actors(db: Session) -> None:
    """Idempotently persist the HarborStone Demo #3 actor identities.

    AIRA and SENTRY are ``AI_AGENT`` actors whose CompliIdentity
    ``principal_id`` is carried in ``wallet_or_agent_account_id``; Jordan Lee
    is ``HUMAN`` and carries it in ``human_principal_id``. That is the field
    ``decision_service._authority_principal_id`` reads to build the
    CompliIdentity authority-context probe. The same id is mirrored into
    ``identity_metadata['compliidentity_principal_id']`` (with tenant and
    source instance) so the linkage is explicit and greppable, not implied
    by an awkwardly-named column.

    The ``principal_id`` values are re-issued whenever the local
    CompliIdentity instance is regenerated, so this refreshes them on the
    existing rows rather than only inserting — the CompliAGL-side ``id`` is
    the stable key.
    """
    rows = (
        (
            HARBORSTONE_AIRA_ACTOR_ID,
            CanonicalActorType.AI_AGENT,
            "AIRA",
            _HARBORSTONE_AIRA_PRINCIPAL_ID,
        ),
        (
            HARBORSTONE_SENTRY_ACTOR_ID,
            CanonicalActorType.AI_AGENT,
            "SENTRY",
            _HARBORSTONE_SENTRY_PRINCIPAL_ID,
        ),
        (
            HARBORSTONE_JORDAN_ACTOR_ID,
            CanonicalActorType.HUMAN,
            "Jordan Lee",
            _HARBORSTONE_JORDAN_PRINCIPAL_ID,
        ),
    )
    for actor_id, actor_type, display_name, principal_id in rows:
        is_human = actor_type == CanonicalActorType.HUMAN
        metadata = {
            "display_name": display_name,
            "demo": "harborstone",
            "compliidentity_principal_id": principal_id,
            "compliidentity_tenant_id": HARBORSTONE_ORG_ID,
            "compliidentity_instance": _COMPLIIDENTITY_INSTANCE,
        }
        actor = db.get(ActorIdentity, actor_id)
        if actor is None:
            actor = ActorIdentity(
                id=actor_id,
                organization_id=HARBORSTONE_ORG_ID,
                actor_type=actor_type.value,
                credential_type=CredentialType.NONE.value,
                verification_status=VerificationStatus.UNVERIFIED.value,
                revocation_status=RevocationStatus.ACTIVE.value,
            )
            db.add(actor)
        actor.human_principal_id = principal_id if is_human else None
        actor.wallet_or_agent_account_id = None if is_human else principal_id
        actor.identity_metadata = json.dumps(metadata)
    db.commit()


def seed_harborstone_package(db: Session) -> None:
    """Idempotently publish the HarborStone Demo #3 governance package.

    Runs ``build_harborstone_package()`` through the real lifecycle
    (create -> validate -> approve -> publish). Skips entirely when a
    PUBLISHED package with the same (name, version) already exists; when an
    *older* version is published it is superseded atomically on publish.

    **This package carries a placeholder sanctions-screening control**
    (``CTL-PLACEHOLDER-SANCTIONS-SCREENING``, ``evaluation_expression:
    "True"`` -- see
    ``PENDING_REVIEW_harborstone_screening_control_placeholder.md``). It is
    scoped to the ``harborstone-demo`` org only and named unambiguously; it
    exists so the decision-engine + CompliIdentity authority-context wiring
    can be exercised end-to-end, and must be replaced with real screening
    content before any actual HarborStone demo run.

    The approve step records ``approved_by="demo3-step2-seed"`` -- a marker
    string. ``governance_package_service.approve()`` does not validate that
    value against any principal, role or authority; the package-approval
    action has no identity check behind it. See
    ``docs/HUMAN_APPROVAL_ORCHESTRATION_GAP.md`` ("Related: package-approval
    layer").
    """
    from app.db.harborstone_package import (
        PACKAGE_NAME,
        PACKAGE_VERSION,
        build_harborstone_package,
    )
    from app.repositories.canonical import (
        ExecutableGovernancePackageRepository,
    )
    from app.services.canonical import governance_package_service
    from app.utils.canonical_enums import PackageStatus

    existing = governance_package_service.get_published_version(
        db, HARBORSTONE_ORG_ID, PACKAGE_NAME, PACKAGE_VERSION
    )
    if existing is not None:
        return

    # If an earlier version of this package is already PUBLISHED for the org,
    # supersede it on publish so there is exactly one active version. (Fresh
    # demo / test DBs have none, so this is a no-op there.)
    prior_published = ExecutableGovernancePackageRepository(db).list_filtered(
        HARBORSTONE_ORG_ID,
        package_name=PACKAGE_NAME,
        status=PackageStatus.PUBLISHED.value,
    )
    create_payload = build_harborstone_package(HARBORSTONE_ORG_ID)
    if prior_published:
        create_payload.supersedes_package_id = prior_published[-1].id

    pkg = governance_package_service.create(db, create_payload)
    result = governance_package_service.validate(db, HARBORSTONE_ORG_ID, pkg.id)
    if not result.valid:
        raise RuntimeError(
            f"HarborStone governance package failed validation: {result.errors}"
        )
    governance_package_service.approve(
        db, HARBORSTONE_ORG_ID, pkg.id, approved_by="demo3-step2-seed"
    )
    governance_package_service.publish(db, HARBORSTONE_ORG_ID, pkg.id)


def seed_demo_data(db: Session) -> None:
    """Seed all canonical demo data (organizations + actors + policies)."""
    seed_organizations(db)
    seed_demo_actors(db)
    seed_demo_policies(db)
    seed_harborstone_actors(db)
    seed_harborstone_package(db)
