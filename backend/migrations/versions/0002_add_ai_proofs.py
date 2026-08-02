"""add canonical ai_proofs table (consolidated AIProof)

Revision ID: 0002_add_ai_proofs
Revises: 0001_baseline
Create Date: 2026-08-02 00:05:00.000000

Introduces the single, canonical persistent proof record ``ai_proofs`` that
consolidates the legacy ``proof_bundles`` (ORM) and the previously in-memory
``AIProofBundle`` domain model.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_add_ai_proofs"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_proofs",
        sa.Column("proof_id", sa.String(), nullable=False),
        sa.Column("proof_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_identity", sa.Text(), nullable=True),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("policy_id", sa.String(), nullable=True),
        sa.Column("policy_version", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=False),
        sa.Column("execution_adapter", sa.String(), nullable=True),
        sa.Column("execution_status", sa.String(), nullable=True),
        sa.Column("payment_protocol", sa.String(), nullable=True),
        sa.Column("payment_reference", sa.String(), nullable=True),
        sa.Column("settlement_chain", sa.String(), nullable=True),
        sa.Column("anchor_chain", sa.String(), nullable=True),
        sa.Column("anchor_tx_id", sa.String(), nullable=True),
        sa.Column("proof_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("verification_url", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("proof_id"),
    )
    with op.batch_alter_table("ai_proofs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ai_proofs_actor_id"), ["actor_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ai_proofs_intent_id"), ["intent_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_ai_proofs_proof_hash"), ["proof_hash"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ai_proofs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ai_proofs_proof_hash"))
        batch_op.drop_index(batch_op.f("ix_ai_proofs_intent_id"))
        batch_op.drop_index(batch_op.f("ix_ai_proofs_actor_id"))
    op.drop_table("ai_proofs")
