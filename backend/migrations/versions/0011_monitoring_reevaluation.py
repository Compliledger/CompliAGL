"""continuous monitoring & automated re-evaluation

Revision ID: 0011_monitoring_reevaluation
Revises: 0010_canonical_aiproof, 0010_integration_events
Create Date: 2026-08-02 17:30:00.000000

Adds the continuous-monitoring branch (and merges the two prior 0010 heads):

* ``monitoring_events`` — immutable change events observed by the continuous
  monitor (change type, source, affected object, before/after state hashes,
  provenance, severity, correlation id).
* ``reevaluation_runs`` — the record of one automated re-evaluation triggered by
  a monitoring event, linking the new immutable records it produced.
* ``canonical_ai_proofs.superseded_by_aiproof_id`` — forward supersession link so
  a superseded proof points at the proof that replaced it.

Every table is tenant-scoped (``organization_id``) and versioned
(``schema_version``).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0011_monitoring_reevaluation"
down_revision: Union[str, Sequence[str], None] = (
    "0010_canonical_aiproof",
    "0010_integration_events",
)
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
    # --- monitoring_events ------------------------------------------------- #
    op.create_table(
        "monitoring_events",
        *_common_columns(),
        sa.Column("event_uid", sa.String(), nullable=False),
        sa.Column("change_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("affected_object_type", sa.String(), nullable=False),
        sa.Column("affected_object_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=True),
        sa.Column("evaluation_id", sa.String(), nullable=True),
        sa.Column("old_state_hash", sa.String(), nullable=True),
        sa.Column("new_state_hash", sa.String(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "severity", sa.String(), nullable=False, server_default="MEDIUM"
        ),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("event_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("monitoring_events", schema=None) as batch_op:
        for column in (
            "organization_id",
            "event_uid",
            "change_type",
            "affected_object_type",
            "affected_object_id",
            "intent_id",
            "evaluation_id",
            "correlation_id",
            "event_hash",
        ):
            _create_index(batch_op, "monitoring_events", column)

    # --- reevaluation_runs ------------------------------------------------- #
    op.create_table(
        "reevaluation_runs",
        *_common_columns(),
        sa.Column("monitoring_event_id", sa.String(), nullable=False),
        sa.Column("change_type", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="PENDING"
        ),
        sa.Column("intent_id", sa.String(), nullable=True),
        sa.Column("evaluation_id", sa.String(), nullable=True),
        sa.Column("impact", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("prior_decision_id", sa.String(), nullable=True),
        sa.Column("new_decision_id", sa.String(), nullable=True),
        sa.Column("new_assessment_id", sa.String(), nullable=True),
        sa.Column("prior_aiproof_id", sa.String(), nullable=True),
        sa.Column("new_aiproof_id", sa.String(), nullable=True),
        sa.Column(
            "invalidated_authorization_ids",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("resulting_outcome", sa.String(), nullable=True),
        sa.Column(
            "reason_codes", sa.Text(), nullable=False, server_default="[]"
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("reevaluation_runs", schema=None) as batch_op:
        for column in (
            "organization_id",
            "monitoring_event_id",
            "change_type",
            "correlation_id",
            "status",
            "intent_id",
            "evaluation_id",
            "prior_decision_id",
            "new_decision_id",
            "new_assessment_id",
            "prior_aiproof_id",
            "new_aiproof_id",
        ):
            _create_index(batch_op, "reevaluation_runs", column)

    # --- canonical_ai_proofs.superseded_by_aiproof_id ---------------------- #
    with op.batch_alter_table("canonical_ai_proofs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("superseded_by_aiproof_id", sa.String(), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_canonical_ai_proofs_superseded_by_aiproof_id"),
            ["superseded_by_aiproof_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("canonical_ai_proofs", schema=None) as batch_op:
        batch_op.drop_index(
            batch_op.f("ix_canonical_ai_proofs_superseded_by_aiproof_id")
        )
        batch_op.drop_column("superseded_by_aiproof_id")
    op.drop_table("reevaluation_runs")
    op.drop_table("monitoring_events")
