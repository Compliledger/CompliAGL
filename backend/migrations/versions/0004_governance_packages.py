"""executable governance packages

Revision ID: 0004_governance_packages
Revises: 0003_canonical_domain
Create Date: 2026-08-02 01:30:00.000000

Adds the persistent table backing the CompliLedger → CompliAGL integration
contract: :class:`ExecutableGovernancePackage`. The table is tenant-scoped
(``organization_id``) and versioned (``schema_version``); executable content
(requirements, applicability rules, control definitions, evidence requirements,
decision conditions, conflict-resolution rules, and metadata) is stored as JSON
text and bound by a deterministic ``package_hash``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_governance_packages"
down_revision: Union[str, None] = "0003_canonical_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "executable_governance_packages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
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
        sa.Column("package_name", sa.String(), nullable=False),
        sa.Column("package_version", sa.String(), nullable=False),
        sa.Column("content_schema_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_package_id", sa.String(), nullable=True),
        sa.Column("superseded_by_package_id", sa.String(), nullable=True),
        sa.Column("package_hash", sa.String(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("signer_key_id", sa.String(), nullable=True),
        sa.Column("source_document_references", sa.Text(), nullable=True),
        sa.Column("source_requirement_references", sa.Text(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("applicability_rules", sa.Text(), nullable=False),
        sa.Column("control_definitions", sa.Text(), nullable=False),
        sa.Column("evidence_requirements", sa.Text(), nullable=False),
        sa.Column("decision_conditions", sa.Text(), nullable=False),
        sa.Column("conflict_resolution_rules", sa.Text(), nullable=False),
        sa.Column("package_metadata", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table(
        "executable_governance_packages", schema=None
    ) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_executable_governance_packages_organization_id"),
            ["organization_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_executable_governance_packages_package_name"),
            ["package_name"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_executable_governance_packages_supersedes_package_id"),
            ["supersedes_package_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f(
                "ix_executable_governance_packages_superseded_by_package_id"
            ),
            ["superseded_by_package_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_executable_governance_packages_package_hash"),
            ["package_hash"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("executable_governance_packages")
