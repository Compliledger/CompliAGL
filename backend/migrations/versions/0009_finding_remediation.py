"""finding + remediation branch persistent domain objects

Revision ID: 0009_finding_remediation
Revises: 0008_decision_authorization_binding
Create Date: 2026-08-02 14:30:00.000000

Adds the persistent tables for the finding-and-remediation branch:
Finding, RemediationPlan, ResolutionEvidence, DevSyncDispatch and ReviewRecord.
Also extends ``decisions`` with ``originating_finding_id`` so a re-assessment
decision references the finding that produced it. Every table is tenant-scoped
(``organization_id``) and versioned (``schema_version``); DevSync is only an
integration surface and never the source of truth for governance state.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009_finding_remediation"
down_revision: Union[str, None] = "0008_decision_authorization_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _common_columns() -> list[sa.Column]:
    return [
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
    ]


def _create_index(batch_op, table: str, column: str) -> None:
    batch_op.create_index(
        batch_op.f(f"ix_{table}_{column}"), [column], unique=False
    )


def upgrade() -> None:
    # --- findings ---------------------------------------------------------- #
    op.create_table(
        "findings",
        *_common_columns(),
        sa.Column("finding_id", sa.String(), nullable=False),
        sa.Column("evaluation_id", sa.String(), nullable=True),
        sa.Column("assessment_id", sa.String(), nullable=True),
        sa.Column("decision_id", sa.String(), nullable=True),
        sa.Column("intent_id", sa.String(), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column(
            "requirement_ids", sa.Text(), nullable=False, server_default="[]"
        ),
        sa.Column("control_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "evidence_gap_ids", sa.Text(), nullable=False, server_default="[]"
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("finding_type", sa.String(), nullable=False),
        sa.Column("decision_impact", sa.String(), nullable=True),
        sa.Column(
            "remediation_eligibility",
            sa.String(),
            nullable=False,
            server_default="ELIGIBLE",
        ),
        sa.Column(
            "terminal", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="OPEN"
        ),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_validation_outcome", sa.String(), nullable=True),
        sa.Column("resolved_by_decision_id", sa.String(), nullable=True),
        sa.Column("reason_codes", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("finding_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("findings", schema=None) as batch_op:
        for column in (
            "organization_id",
            "finding_id",
            "evaluation_id",
            "assessment_id",
            "decision_id",
            "intent_id",
            "actor_id",
            "target_id",
            "finding_type",
            "owner",
            "resolved_by_decision_id",
            "finding_hash",
        ):
            _create_index(batch_op, "findings", column)

    # --- remediation_plans ------------------------------------------------- #
    op.create_table(
        "remediation_plans",
        *_common_columns(),
        sa.Column("remediation_plan_id", sa.String(), nullable=False),
        sa.Column("finding_id", sa.String(), nullable=False),
        sa.Column("required_corrective_state", sa.Text(), nullable=True),
        sa.Column(
            "remediation_actions",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "required_resolution_evidence",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column(
            "priority", sa.String(), nullable=False, server_default="MEDIUM"
        ),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "dependencies", sa.Text(), nullable=False, server_default="[]"
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="OPEN"),
        sa.Column("plan_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("remediation_plans", schema=None) as batch_op:
        for column in (
            "organization_id",
            "remediation_plan_id",
            "finding_id",
            "owner",
            "plan_hash",
        ):
            _create_index(batch_op, "remediation_plans", column)

    # --- resolution_evidence ----------------------------------------------- #
    op.create_table(
        "resolution_evidence",
        *_common_columns(),
        sa.Column("finding_id", sa.String(), nullable=False),
        sa.Column("remediation_plan_id", sa.String(), nullable=True),
        sa.Column("evidence_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=True),
        sa.Column("subject_id", sa.String(), nullable=True),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("intent_id", sa.String(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("payload_reference", sa.String(), nullable=True),
        sa.Column("payload_hash", sa.String(), nullable=True),
        sa.Column("claims", sa.Text(), nullable=True),
        sa.Column(
            "sensitivity", sa.String(), nullable=False, server_default="INTERNAL"
        ),
        sa.Column("issuer", sa.String(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column(
            "provenance", sa.Text(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "collection_status",
            sa.String(),
            nullable=False,
            server_default="COLLECTED",
        ),
        sa.Column("validation_outcome", sa.String(), nullable=True),
        sa.Column(
            "validation_checks", sa.Text(), nullable=False, server_default="{}"
        ),
        sa.Column("normalized_claims", sa.Text(), nullable=True),
        sa.Column("reason_codes", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("submitted_via", sa.String(), nullable=True),
        sa.Column("result_hash", sa.String(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("resolution_evidence", schema=None) as batch_op:
        for column in (
            "organization_id",
            "finding_id",
            "remediation_plan_id",
            "evidence_type",
            "source_id",
            "source_type",
            "subject_id",
            "target_id",
            "intent_id",
            "payload_hash",
            "validation_outcome",
            "result_hash",
        ):
            _create_index(batch_op, "resolution_evidence", column)

    # --- devsync_dispatches ------------------------------------------------ #
    op.create_table(
        "devsync_dispatches",
        *_common_columns(),
        sa.Column("finding_id", sa.String(), nullable=False),
        sa.Column("remediation_plan_id", sa.String(), nullable=True),
        sa.Column("adapter", sa.String(), nullable=False),
        sa.Column("external_reference", sa.String(), nullable=True),
        sa.Column("callback_reference", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="PENDING"
        ),
        sa.Column("last_callback_status", sa.String(), nullable=True),
        sa.Column("callbacks", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_callback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("devsync_dispatches", schema=None) as batch_op:
        for column in (
            "organization_id",
            "finding_id",
            "remediation_plan_id",
            "external_reference",
            "callback_reference",
            "payload_hash",
        ):
            _create_index(batch_op, "devsync_dispatches", column)

    # --- review_records ---------------------------------------------------- #
    op.create_table(
        "review_records",
        *_common_columns(),
        sa.Column("finding_id", sa.String(), nullable=True),
        sa.Column("decision_id", sa.String(), nullable=True),
        sa.Column("intent_id", sa.String(), nullable=True),
        sa.Column(
            "review_type",
            sa.String(),
            nullable=False,
            server_default="MANUAL_REVIEW",
        ),
        sa.Column("reviewer_id", sa.String(), nullable=False),
        sa.Column("reviewer_role", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("review_records", schema=None) as batch_op:
        for column in (
            "organization_id",
            "finding_id",
            "decision_id",
            "intent_id",
            "reviewer_id",
            "review_hash",
        ):
            _create_index(batch_op, "review_records", column)

    # --- decisions.originating_finding_id ---------------------------------- #
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("originating_finding_id", sa.String(), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_decisions_originating_finding_id"),
            ["originating_finding_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_decisions_originating_finding_id"))
        batch_op.drop_column("originating_finding_id")

    op.drop_table("review_records")
    op.drop_table("devsync_dispatches")
    op.drop_table("resolution_evidence")
    op.drop_table("remediation_plans")
    op.drop_table("findings")
