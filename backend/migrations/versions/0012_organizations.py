"""organizations — real, validated tenant registry

Revision ID: 0012_organizations
Revises: 0011_monitoring_reevaluation
Create Date: 2026-08-17 18:00:00.000000

Adds ``organizations``, the real tenant registry that every canonical
``organization_id`` column is validated against going forward (see
``app.services.canonical.organization_service``). Previously
``organization_id`` was an unvalidated free-text string.

Seeds two rows:

* ``default-org`` — the tenant every existing canonical record already uses,
  so pre-existing data stays valid once validation is enforced.
* ``securerob-pilot`` — the real, dedicated tenant for the SecureRob pilot.

Then backfills every canonical table currently holding SecureRob-pilot data
(all of it was created under ``default-org`` before this tenant existed) to
point at ``securerob-pilot`` instead. ``evidence_sources`` is handled
separately: it also holds a handful of generic, non-pilot-specific simulator
connector registrations, so only the row for the real pilot connector
(``connector_id = 'securerob-perception-gateway'``) moves; the simulator rows
stay on ``default-org``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0012_organizations"
down_revision: Union[str, Sequence[str], None] = "0011_monitoring_reevaluation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables entirely backfilled from 'default-org' to 'securerob-pilot'.
# (evidence_sources is handled separately below — it's a mixed registry.)
_PILOT_TABLES = (
    "actor_identities",
    "applicability_evaluations",
    "applicable_control_sets",
    "assessments",
    "canonical_evidence_packages",
    "control_evaluations",
    "decisions",
    "evidence_collection_jobs",
    "evidence_orchestration_plans",
    "evidence_requirement_sets",
    "evidence_sufficiency_results",
    "evidence_validation_results",
    "executable_governance_packages",
    "execution_authorizations",
    "governance_evaluations",
    "intents",
    "normalized_evidence",
    "operational_contexts",
    "policy_resolutions",
    "raw_evidence",
    "targets",
)

_DEFAULT_ORG = "default-org"
_PILOT_ORG = "securerob-pilot"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("organization_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )

    organizations = sa.table(
        "organizations",
        sa.column("organization_id", sa.String()),
        sa.column("organization_name", sa.String()),
        sa.column("status", sa.String()),
    )
    op.bulk_insert(
        organizations,
        [
            {
                "organization_id": _DEFAULT_ORG,
                "organization_name": "Default Organization",
                "status": "ACTIVE",
            },
            {
                "organization_id": _PILOT_ORG,
                "organization_name": "SecureRob Pilot",
                "status": "ACTIVE",
            },
        ],
    )

    for table_name in _PILOT_TABLES:
        table = sa.table(
            table_name, sa.column("organization_id", sa.String())
        )
        op.execute(
            table.update()
            .where(table.c.organization_id == _DEFAULT_ORG)
            .values(organization_id=_PILOT_ORG)
        )

    evidence_sources = sa.table(
        "evidence_sources",
        sa.column("organization_id", sa.String()),
        sa.column("connector_id", sa.String()),
    )
    op.execute(
        evidence_sources.update()
        .where(
            sa.and_(
                evidence_sources.c.organization_id == _DEFAULT_ORG,
                evidence_sources.c.connector_id == "securerob-perception-gateway",
            )
        )
        .values(organization_id=_PILOT_ORG)
    )


def downgrade() -> None:
    evidence_sources = sa.table(
        "evidence_sources",
        sa.column("organization_id", sa.String()),
        sa.column("connector_id", sa.String()),
    )
    op.execute(
        evidence_sources.update()
        .where(
            sa.and_(
                evidence_sources.c.organization_id == _PILOT_ORG,
                evidence_sources.c.connector_id == "securerob-perception-gateway",
            )
        )
        .values(organization_id=_DEFAULT_ORG)
    )

    for table_name in _PILOT_TABLES:
        table = sa.table(
            table_name, sa.column("organization_id", sa.String())
        )
        op.execute(
            table.update()
            .where(table.c.organization_id == _PILOT_ORG)
            .values(organization_id=_DEFAULT_ORG)
        )

    op.drop_table("organizations")
