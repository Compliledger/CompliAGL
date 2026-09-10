"""governance package approval-authority fields

Revision ID: 0018_package_approval_authority
Revises: 0017_decision_approval_binding
Create Date: 2026-09-06 00:30:00.000000

Adds two nullable columns to ``executable_governance_packages``:

* ``approval_rationale`` -- the required free-text reason recorded when a
  package is approved (``approved_by`` now holds the approving principal id).
* ``approver_authority_hash`` -- content hash of the approver's CompliIdentity
  authority snapshot, bound into the package the same way
  ``Decision.authority_hash`` is. Null unless
  ``GOVERNANCE_APPROVAL_AUTHORITY_REQUIRED`` was set at approval time.

Both nullable, no server default: null is every package approved before this
change and every approval made with the authority check disabled.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0018_package_approval_authority"
down_revision: Union[str, Sequence[str], None] = "0017_decision_approval_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    sa.Column("approval_rationale", sa.Text(), nullable=True),
    sa.Column("approver_authority_hash", sa.String(), nullable=True),
]


def upgrade() -> None:
    with op.batch_alter_table(
        "executable_governance_packages", schema=None
    ) as batch_op:
        for column in _COLUMNS:
            batch_op.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table(
        "executable_governance_packages", schema=None
    ) as batch_op:
        for column in reversed(_COLUMNS):
            batch_op.drop_column(column.name)
