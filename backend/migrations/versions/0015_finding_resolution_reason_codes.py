"""finding resolution-phase reason codes

Revision ID: 0015_finding_resolution_reason_codes
Revises: 0014_decision_authority_context
Create Date: 2026-09-06 00:00:00.000000

Adds ``resolution_reason_codes`` (nullable JSON text) to ``findings``. Populated
by the resolution phase (resolution validation / re-assessment) to record *why*
a resolution attempt was rejected or a re-assessment was blocked — so a
fail-closed rejection leaves a persisted, queryable trace rather than a reason
that is only returned from a function call and discarded.

Nullable, no server default: ``NULL`` means the resolution phase has not written
to it. Not part of ``finding_hash`` (a post-generation mutation, same as
``resolution_validation_outcome``).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0015_finding_resolution_reason_codes"
down_revision: Union[str, Sequence[str], None] = "0014_decision_authority_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    sa.Column("resolution_reason_codes", sa.Text(), nullable=True),
]


def upgrade() -> None:
    with op.batch_alter_table("findings", schema=None) as batch_op:
        for column in _COLUMNS:
            batch_op.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("findings", schema=None) as batch_op:
        for column in reversed(_COLUMNS):
            batch_op.drop_column(column.name)
