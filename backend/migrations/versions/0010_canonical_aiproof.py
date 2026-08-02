"""canonical AIProof persistent table

Revision ID: 0010_canonical_aiproof
Revises: 0009_finding_remediation
Create Date: 2026-08-02 15:00:00.000000

Adds the single, canonical persistent AIProof table (``canonical_ai_proofs``).
The full canonical AIProof (all governance-lifecycle projections) is stored as
canonical JSON in ``canonical_aiproof``; the remaining columns are indexed
projections used for lookup, history, verification and the CompliLedger handoff.
The table is tenant-scoped (``organization_id``) and versioned
(``schema_version``).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010_canonical_aiproof"
down_revision: Union[str, None] = "0009_finding_remediation"
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
    op.create_table(
        "canonical_ai_proofs",
        *_common_columns(),
        sa.Column("proof_schema_version", sa.String(), nullable=False),
        sa.Column("proof_type", sa.String(), nullable=False),
        sa.Column("governed_outcome", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("handoff_status", sa.String(), nullable=False),
        sa.Column("canonicalization_algorithm", sa.String(), nullable=False),
        sa.Column("hash_algorithm", sa.String(), nullable=False),
        sa.Column("aiproof_hash", sa.String(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("signer_key_id", sa.String(), nullable=False),
        sa.Column("issuer", sa.String(), nullable=False),
        sa.Column("canonical_aiproof", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("governance_evaluation_id", sa.String(), nullable=True),
        sa.Column("actor_identity_id", sa.String(), nullable=True),
        sa.Column("intent_id", sa.String(), nullable=True),
        sa.Column("decision_id", sa.String(), nullable=True),
        sa.Column("prior_aiproof_id", sa.String(), nullable=True),
        sa.Column("requested_proof_policy", sa.String(), nullable=True),
        sa.Column("privacy_classification", sa.String(), nullable=True),
        sa.Column("handoff_reference", sa.String(), nullable=True),
        sa.Column("handoff_detail", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handoff_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("canonical_ai_proofs", schema=None) as batch_op:
        for column in (
            "organization_id",
            "governed_outcome",
            "status",
            "handoff_status",
            "aiproof_hash",
            "correlation_id",
            "governance_evaluation_id",
            "actor_identity_id",
            "intent_id",
            "decision_id",
            "prior_aiproof_id",
        ):
            _create_index(batch_op, "canonical_ai_proofs", column)


def downgrade() -> None:
    op.drop_table("canonical_ai_proofs")
