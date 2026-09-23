"""Persistent demo seed data.

Seeds the **database** (not an in-memory registry) with a canonical demo actor
and policy so the Compli402 governance flow works out of the box. Seeding is
idempotent and, because it is persisted, survives application restarts.

This replaces the deprecated in-memory ``seed_demo_actors`` /
``seed_demo_policies`` helpers.
"""

from __future__ import annotations

import json
import os
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
# step2_live.db`` instance (see ``demo3_step2/compliidentity_setup_phases_1_7.py``
# and its ``compliidentity_setup_results.json``). Regenerating that instance
# re-issues these; update the three values here when that happens. Refreshed
# 2026-09-16 against a freshly-regenerated instance.
_COMPLIIDENTITY_INSTANCE = "compliidentity_demo3_step2_live.db"
_HARBORSTONE_AIRA_PRINCIPAL_ID = "3d5366bd-3bb4-44d5-8108-1759e6fe45f3"
_HARBORSTONE_SENTRY_PRINCIPAL_ID = "ea0c8c69-a745-4b6a-85aa-aa5c3bb22958"
_HARBORSTONE_JORDAN_PRINCIPAL_ID = "91a86c47-27ec-4c09-afda-3ac7dc618589"

# These three ids are only ever correct for whichever local/dev CompliIdentity
# instance was last regenerated -- they must never overwrite a real
# production principal_id. seed_demo_data() (called unconditionally on every
# boot, see app/main.py's lifespan hook -- there is no separate "prod main")
# skips seed_harborstone_actors() entirely in production for exactly this
# reason; see _is_production() below. A direct call to
# seed_harborstone_actors() (every test, and demo3_step2/compliagl_scenarios.py)
# is unaffected by this gate.

# --- Circle Grant MVP (PR 3a) ---------------------------------------------- #
# Stable CompliAGL-side ids for the Circle demo org and its Treasury Agent.
# Unlike HarborStone's actors, this agent carries no CompliIdentity
# principal_id at all -- the package sets requires_authority_context: false
# and delegated authority lives entirely in identity_metadata (docs/dev-
# rules.md rule 6) -- so there is no principal-id-clobbering risk to gate on.
# Instead, all three Circle seeds are gated behind ENABLE_CIRCLE_MVP (see
# _circle_mvp_enabled() below): the demo is opt-in, and while opted in, the
# agent's identity_metadata is deliberately reset to the fixed demo values on
# every boot so the demo stays deterministic.
CIRCLE_ORG_ID = "circle-mvp-demo"
CIRCLE_TREASURY_AGENT_ID = "circle-mvp-treasury-agent"
_CIRCLE_TREASURY_AGENT_ACCOUNT_ID = "circle-treasury-agent-wallet-001"


def _is_production() -> bool:
    """True when this process is a production deployment.

    Checked directly against ``os.environ`` (not ``app.core.config.settings``,
    which has no such field) so this also self-activates on Railway without
    requiring a separately-configured env var: an explicit ``ENVIRONMENT``
    always wins when set, otherwise Railway's own auto-injected environment
    name is used (the exact var name changed across Railway versions, so both
    are checked).
    """
    for var in ("ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT"):
        value = os.environ.get(var)
        if value:
            return value.strip().lower() == "production"
    return False


def _circle_mvp_enabled() -> bool:
    """True when the Circle Grant MVP demo (org, Treasury Agent, package) is
    opted in via ``ENABLE_CIRCLE_MVP``. Independent of ``_is_production()`` --
    this is a feature flag, not a prod/non-prod distinction."""
    return os.environ.get("ENABLE_CIRCLE_MVP", "").strip().lower() == "true"


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
    *older* version is published it is superseded atomically on publish
    (so a boot after the v1.2.x bump supersedes any published v1.1.0).

    The package's sanctions-screening requirement/control
    (``REQ`` / ``CTL-HARBORSTONE-SANCTIONS-SCREENING``) is real, keyed to
    SENTRY's structured screening evidence
    (``harborstone.sanctions_screening.v1``). The screening *lookup* is a
    deterministic in-repo demo dataset (project-owner-approved for the MVP,
    labelled as simulation on every evidence item) -- see
    ``docs/harborstone-sanctions-screening.md``.

    The approve step records a seed-bootstrap approver id + rationale. When
    ``GOVERNANCE_APPROVAL_AUTHORITY_REQUIRED`` is set, this seed would fail
    closed (a bootstrap marker is not a CompliIdentity principal with
    governance.package/approve authority) -- which is correct: a locked-down
    deployment should not auto-approve governance from seed data.
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
        db,
        HARBORSTONE_ORG_ID,
        pkg.id,
        approver_principal_id="seed-bootstrap",
        rationale="Seeded on boot for the Demo #3 HarborStone scenario.",
    )
    governance_package_service.publish(db, HARBORSTONE_ORG_ID, pkg.id)


def seed_hedera_demo_package(db: Session) -> None:
    """Idempotently publish the Hedera Agent Kit demo governance package.

    Backs demo.compliagl.compliledger.com and the local
    CompliAGL-Hedera-Agent-Kit-Adapter e2e demo. Runs
    build_hedera_demo_package() through the real lifecycle
    (create -> validate -> approve -> publish). Skips entirely when a
    PUBLISHED package with the same (name, version) already exists.

    Without this, the package silently disappears on every restart
    (this backend's SQLite persistence is recreated on redeploy) and
    both demos start returning DENY with reason code NO_APPLICABLE_POLICY
    until someone notices and manually republishes it.
    """
    from app.db.hedera_demo_package import (
        PACKAGE_NAME,
        PACKAGE_VERSION,
        build_hedera_demo_package,
    )
    from app.repositories.canonical import (
        ExecutableGovernancePackageRepository,
    )
    from app.services.canonical import governance_package_service
    from app.utils.canonical_enums import PackageStatus

    organization_id = "default-org"

    existing = governance_package_service.get_published_version(
        db, organization_id, PACKAGE_NAME, PACKAGE_VERSION
    )
    if existing is not None:
        return

    prior_published = ExecutableGovernancePackageRepository(db).list_filtered(
        organization_id,
        package_name=PACKAGE_NAME,
        status=PackageStatus.PUBLISHED.value,
    )
    create_payload = build_hedera_demo_package(organization_id)
    if prior_published:
        create_payload.supersedes_package_id = prior_published[-1].id

    pkg = governance_package_service.create(db, create_payload)
    result = governance_package_service.validate(db, organization_id, pkg.id)
    if not result.valid:
        raise RuntimeError(
            f"Hedera demo governance package failed validation: {result.errors}"
        )
    governance_package_service.approve(
        db,
        organization_id,
        pkg.id,
        approver_principal_id="seed-bootstrap",
        rationale="Seeded on boot for the Hedera Agent Kit demo.",
    )
    governance_package_service.publish(db, organization_id, pkg.id)


def seed_circle_org(db: Session) -> None:
    """Idempotently persist the Circle Grant MVP demo organization."""
    org = db.get(Organization, CIRCLE_ORG_ID)
    if org is None:
        db.add(
            Organization(
                organization_id=CIRCLE_ORG_ID,
                organization_name="Circle Grant MVP",
                status="ACTIVE",
            )
        )
    db.commit()


def seed_circle_treasury_agent(db: Session) -> None:
    """Idempotently persist the Circle Treasury Agent actor identity.

    ``VERIFIED`` / not revoked, and carries its delegated authority directly
    in ``identity_metadata.delegated_authority`` (docs/dev-rules.md rule 6 --
    no CompliIdentity principal_id, no authority-context call). Refreshed in
    place on every call while ``ENABLE_CIRCLE_MVP`` is on, same as
    ``seed_harborstone_actors``, so the demo's delegated-authority limits stay
    deterministic. Only ever touches this one row under ``CIRCLE_ORG_ID``.
    """
    metadata = {
        "display_name": "Circle Treasury Agent",
        "demo": "circle-mvp",
        "delegated_authority": {
            "allowed_actions": ["USDC_TRANSFER"],
            "allowed_assets": ["USDC"],
            "allowed_networks": ["ARC"],
            "autonomous_limit_minor": 10_000_000,
        },
    }
    actor = db.get(ActorIdentity, CIRCLE_TREASURY_AGENT_ID)
    if actor is None:
        actor = ActorIdentity(
            id=CIRCLE_TREASURY_AGENT_ID,
            organization_id=CIRCLE_ORG_ID,
            actor_type=CanonicalActorType.AI_AGENT.value,
            credential_type=CredentialType.NONE.value,
            verification_status=VerificationStatus.VERIFIED.value,
            revocation_status=RevocationStatus.ACTIVE.value,
        )
        db.add(actor)
    actor.human_principal_id = None
    actor.wallet_or_agent_account_id = _CIRCLE_TREASURY_AGENT_ACCOUNT_ID
    actor.verification_status = VerificationStatus.VERIFIED.value
    actor.revocation_status = RevocationStatus.ACTIVE.value
    actor.identity_metadata = json.dumps(metadata)
    db.commit()


def seed_circle_package(db: Session) -> None:
    """Idempotently publish the Circle treasury governance package.

    Same create -> validate -> approve -> publish lifecycle as
    ``seed_harborstone_package``; skips entirely when a PUBLISHED package
    with the same (name, version) already exists, and supersedes an older
    published version on publish.
    """
    from app.db.circle_treasury_package import (
        PACKAGE_NAME,
        PACKAGE_VERSION,
        build_circle_treasury_package,
    )
    from app.repositories.canonical import (
        ExecutableGovernancePackageRepository,
    )
    from app.services.canonical import governance_package_service
    from app.utils.canonical_enums import PackageStatus

    existing = governance_package_service.get_published_version(
        db, CIRCLE_ORG_ID, PACKAGE_NAME, PACKAGE_VERSION
    )
    if existing is not None:
        return

    prior_published = ExecutableGovernancePackageRepository(db).list_filtered(
        CIRCLE_ORG_ID,
        package_name=PACKAGE_NAME,
        status=PackageStatus.PUBLISHED.value,
    )
    create_payload = build_circle_treasury_package(CIRCLE_ORG_ID)
    if prior_published:
        create_payload.supersedes_package_id = prior_published[-1].id

    pkg = governance_package_service.create(db, create_payload)
    result = governance_package_service.validate(db, CIRCLE_ORG_ID, pkg.id)
    if not result.valid:
        raise RuntimeError(
            f"Circle treasury governance package failed validation: {result.errors}"
        )
    governance_package_service.approve(
        db,
        CIRCLE_ORG_ID,
        pkg.id,
        approver_principal_id="seed-bootstrap",
        rationale="Seeded on boot for the Circle Grant MVP demo.",
    )
    governance_package_service.publish(db, CIRCLE_ORG_ID, pkg.id)


def seed_demo_data(db: Session) -> None:
    """Seed all canonical demo data (organizations + actors + policies).

    ``seed_harborstone_actors`` is skipped in production: it unconditionally
    refreshes ``human_principal_id`` / ``wallet_or_agent_account_id`` on the
    three HarborStone actor rows from the local-dev/demo constants above on
    every call, which would silently clobber a real production principal_id
    on every boot. Everything else here is safe to run everywhere -- it only
    creates rows that don't yet exist (orgs, the demo travel actors/policy)
    or supersedes an outdated package version, never overwrites an identity
    field on an existing row.
    """
    seed_organizations(db)
    seed_demo_actors(db)
    seed_demo_policies(db)
    if not _is_production():
        seed_harborstone_actors(db)
    seed_harborstone_package(db)
    seed_hedera_demo_package(db)
    if _circle_mvp_enabled():
        seed_circle_org(db)
        seed_circle_treasury_agent(db)
        seed_circle_package(db)