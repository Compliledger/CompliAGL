"""decision authority-context binding fields

Revision ID: 0014_decision_authority_context
Revises: 0013_governance_package_authority_flag
Create Date: 2026-09-05 00:05:00.000000

Adds ``authority_status`` / ``authority_reason`` / ``authority_hash`` to
``decisions``, following the same content-hash binding pattern already used
for ``actor_hash`` / ``intent_hash`` / ``target_hash`` / ``context_hash``
(see migration 0008). All nullable: null means the governing package didn't
set ``requires_authority_context`` and no CompliIdentity call was made for
that decision.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0014_decision_authority_context"
down_revision: Union[str, Sequence[str], None] = (
    "0013_governance_package_authority_flag"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    sa.Column("authority_status", sa.String(), nullable=True),
    sa.Column("authority_reason", sa.String(), nullable=True),
    sa.Column("authority_hash", sa.String(), nullable=True),
]


def upgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        for column in _COLUMNS:
            batch_op.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        for column in reversed(_COLUMNS):
            batch_op.drop_column(column.name)
