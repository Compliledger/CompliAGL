"""escalation approvals persistent table

Revision ID: 0016_escalation_approvals
Revises: 0015_finding_resolution_reason_codes
Create Date: 2026-09-06 00:10:00.000000

Adds the ``escalation_approvals`` table: the durable record of a human approving
an ``ESCALATED`` decision that escalated for human approval. Only ever written
after the approver's authority to approve *this* action has been verified
against CompliIdentity at approval time; time-bounded via ``valid_until`` and
consumed by exactly one re-decision.

Tenant-scoped (``organization_id``) and versioned (``schema_version``) like every
canonical resource.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0016_escalation_approvals"
down_revision: Union[str, Sequence[str], None] = (
    "0015_finding_resolution_reason_codes"
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


_INDEXED = (
    "organization_id",
    "escalation_approval_id",
    "decision_id",
    "intent_id",
    "approver_principal_id",
    "consumed_by_decision_id",
    "approval_hash",
)


def upgrade() -> None:
    op.create_table(
        "escalation_approvals",
        *_common_columns(),
        sa.Column("escalation_approval_id", sa.String(), nullable=False),
        sa.Column("decision_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=True),
        sa.Column("approver_principal_id", sa.String(), nullable=False),
        sa.Column("approver_principal_type", sa.String(), nullable=True),
        sa.Column("approver_authority_hash", sa.String(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="ACTIVE"
        ),
        sa.Column("consumed_by_decision_id", sa.String(), nullable=True),
        sa.Column("approval_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("escalation_approvals", schema=None) as batch_op:
        for column in _INDEXED:
            _create_index(batch_op, "escalation_approvals", column)


def downgrade() -> None:
    op.drop_table("escalation_approvals")
