"""control determination and evidence requirement resolution

Revision ID: 0006_control_evidence_sets
Revises: 0005_policy_resolution_applicability
Create Date: 2026-08-02 12:10:00.000000

Adds the persistent tables backing the two deterministic runtime stages that
run after Applicability Evaluation and before evidence collection:

* :class:`ApplicableControlSet` — the controls determined applicable for a
  policy resolution (controls mapped to APPLICABLE / conditionally applicable
  requirements, with CONDITIONAL / INDETERMINATE status preserved).
* :class:`EvidenceRequirementSet` — the evidence requirements resolved for the
  applicable controls (REQUIRED / OPTIONAL / CONDITIONAL / NOT_REQUIRED /
  UNRESOLVED).

Both tables are tenant-scoped (``organization_id``) and versioned
(``schema_version``); structured fields are stored as JSON text and bound by
deterministic ``input_hash`` / ``result_hash`` values.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_control_evidence_sets"
down_revision: Union[str, None] = "0005_policy_resolution_applicability"
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


def upgrade() -> None:
    op.create_table(
        "applicable_control_sets",
        *_common_columns(),
        sa.Column("policy_resolution_id", sa.String(), nullable=False),
        sa.Column("actor_identity_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("operational_context_id", sa.String(), nullable=True),
        sa.Column("controls", sa.Text(), nullable=False),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("result_hash", sa.String(), nullable=True),
        sa.Column("determined_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("applicable_control_sets", schema=None) as batch_op:
        for column in (
            "organization_id",
            "policy_resolution_id",
            "actor_identity_id",
            "intent_id",
            "target_id",
            "operational_context_id",
            "input_hash",
            "result_hash",
        ):
            batch_op.create_index(
                batch_op.f(f"ix_applicable_control_sets_{column}"),
                [column],
                unique=False,
            )

    op.create_table(
        "evidence_requirement_sets",
        *_common_columns(),
        sa.Column("policy_resolution_id", sa.String(), nullable=False),
        sa.Column("applicable_control_set_id", sa.String(), nullable=False),
        sa.Column("actor_identity_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("operational_context_id", sa.String(), nullable=True),
        sa.Column("evidence_requirements", sa.Text(), nullable=False),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("result_hash", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table(
        "evidence_requirement_sets", schema=None
    ) as batch_op:
        for column in (
            "organization_id",
            "policy_resolution_id",
            "applicable_control_set_id",
            "actor_identity_id",
            "intent_id",
            "target_id",
            "operational_context_id",
            "input_hash",
            "result_hash",
        ):
            batch_op.create_index(
                batch_op.f(f"ix_evidence_requirement_sets_{column}"),
                [column],
                unique=False,
            )


def downgrade() -> None:
    op.drop_table("evidence_requirement_sets")
    op.drop_table("applicable_control_sets")
