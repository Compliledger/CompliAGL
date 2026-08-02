"""policy resolution and applicability evaluation

Revision ID: 0005_policy_resolution_applicability
Revises: 0004_governance_packages
Create Date: 2026-08-02 12:00:00.000000

Adds the persistent tables backing the two deterministic runtime stages that
precede the decision engine:

* :class:`PolicyResolution` — the governing package versions selected for a
  concrete (actor, intent, target, context) tuple.
* :class:`ApplicabilityEvaluation` — the per-requirement deterministic
  applicability result (APPLICABLE / NOT_APPLICABLE / CONDITIONAL /
  INDETERMINATE).

Both tables are tenant-scoped (``organization_id``) and versioned
(``schema_version``); structured fields are stored as JSON text and bound by
deterministic ``input_hash`` / ``result_hash`` values.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_policy_resolution_applicability"
down_revision: Union[str, None] = "0004_governance_packages"
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
        "policy_resolutions",
        *_common_columns(),
        sa.Column("actor_identity_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("operational_context_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("candidate_package_ids", sa.Text(), nullable=False),
        sa.Column("selected_packages", sa.Text(), nullable=False),
        sa.Column("conflicts", sa.Text(), nullable=False),
        sa.Column("selection_facts", sa.Text(), nullable=True),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("result_hash", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("policy_resolutions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_policy_resolutions_organization_id"),
            ["organization_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_policy_resolutions_actor_identity_id"),
            ["actor_identity_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_policy_resolutions_intent_id"),
            ["intent_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_policy_resolutions_target_id"),
            ["target_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_policy_resolutions_operational_context_id"),
            ["operational_context_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_policy_resolutions_input_hash"),
            ["input_hash"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_policy_resolutions_result_hash"),
            ["result_hash"],
            unique=False,
        )

    op.create_table(
        "applicability_evaluations",
        *_common_columns(),
        sa.Column("policy_resolution_id", sa.String(), nullable=False),
        sa.Column("actor_identity_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("operational_context_id", sa.String(), nullable=True),
        sa.Column("package_id", sa.String(), nullable=False),
        sa.Column("package_version", sa.String(), nullable=False),
        sa.Column("requirement_id", sa.String(), nullable=False),
        sa.Column("requirement_version", sa.String(), nullable=True),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("evaluated_expression", sa.Text(), nullable=True),
        sa.Column("observed_values", sa.Text(), nullable=False),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("result_hash", sa.String(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table(
        "applicability_evaluations", schema=None
    ) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_organization_id"),
            ["organization_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_policy_resolution_id"),
            ["policy_resolution_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_actor_identity_id"),
            ["actor_identity_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_intent_id"),
            ["intent_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_target_id"),
            ["target_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_operational_context_id"),
            ["operational_context_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_package_id"),
            ["package_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_requirement_id"),
            ["requirement_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_input_hash"),
            ["input_hash"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_applicability_evaluations_result_hash"),
            ["result_hash"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("applicability_evaluations")
    op.drop_table("policy_resolutions")
