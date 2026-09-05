"""governance package requires_authority_context flag

Revision ID: 0013_governance_package_authority_flag
Revises: 0012_organizations
Create Date: 2026-09-05 00:00:00.000000

Adds ``requires_authority_context`` to ``executable_governance_packages``.
Opt-in, defaults False: only packages that explicitly declare it will trigger
a CompliIdentity authority-context call at decision time (see
``app.services.canonical.authority_context_service`` and
``decision_service.py``). Every package published before this migration
defaults to False and is unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0013_governance_package_authority_flag"
down_revision: Union[str, Sequence[str], None] = "0012_organizations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table(
        "executable_governance_packages", schema=None
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "requires_authority_context",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "executable_governance_packages", schema=None
    ) as batch_op:
        batch_op.drop_column("requires_authority_context")
