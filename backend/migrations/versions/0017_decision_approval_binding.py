"""decision escalation-approval binding fields

Revision ID: 0017_decision_approval_binding
Revises: 0016_escalation_approvals
Create Date: 2026-09-06 00:20:00.000000

Adds two nullable columns to ``decisions`` for human-approval orchestration:

* ``required_approver_types`` -- JSON string list of the approver principal
  type(s) CompliIdentity declared were required to approve the escalated
  action (distilled from the authority context's ``applicable_approvals`` at
  decision time). Read back by ``escalation_approval_service`` to confirm a
  submitted approver is the *required* type, not just a human.
* ``approval_hash`` -- content hash of the ``approval`` runtime fact, folded
  into ``input_hash`` the same way ``authority_hash`` is (migration 0014).
  Null unless the decision is a re-decision that consumed an approval.

Both nullable, no server default: null is the pre-orchestration state and the
state for every decision that isn't authority-gated / isn't a re-decision.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017_decision_approval_binding"
down_revision: Union[str, Sequence[str], None] = "0016_escalation_approvals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    sa.Column("required_approver_types", sa.Text(), nullable=True),
    sa.Column("approval_hash", sa.String(), nullable=True),
]


def upgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        for column in _COLUMNS:
            batch_op.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        for column in reversed(_COLUMNS):
            batch_op.drop_column(column.name)
