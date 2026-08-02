"""decision + execution authorization binding fields

Revision ID: 0008_decision_authorization_binding
Revises: 0007_sufficiency_evaluation_assessment
Create Date: 2026-08-02 13:30:00.000000

Extends the ``decisions`` and ``execution_authorizations`` tables so the
canonical Decision stage and the signed ExecutionAuthorization resource carry
their full deterministic field sets:

* ``decisions`` — evaluation / assessment linkage, the explicit decision
  conditions triggered, applicable package / requirement / control-evaluation
  ids, bound evidence + input hashes, the deterministic engine version, decision
  expiry, and immutable supersession state.
* ``execution_authorizations`` — narrow action binding (actor / target / action /
  parameter constraints / amount cap / permitted execution system), replay +
  idempotency + one-time-use lifecycle fields (nonce, idempotency key,
  issued/consumed/revoked timestamps), the bound policy / assessment / evidence /
  decision hashes, and the signature (signer key id, signature, authorization
  hash).

All new columns are nullable so existing rows remain valid.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008_decision_authorization_binding"
down_revision: Union[str, None] = "0007_sufficiency_evaluation_assessment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DECISION_COLUMNS = [
    sa.Column("evaluation_id", sa.String(), nullable=True),
    sa.Column("policy_resolution_id", sa.String(), nullable=True),
    sa.Column("assessment_id", sa.String(), nullable=True),
    sa.Column(
        "decision_conditions_triggered",
        sa.Text(),
        nullable=False,
        server_default="[]",
    ),
    sa.Column(
        "applicable_package_ids", sa.Text(), nullable=False, server_default="[]"
    ),
    sa.Column(
        "applicable_requirement_ids",
        sa.Text(),
        nullable=False,
        server_default="[]",
    ),
    sa.Column(
        "control_evaluation_ids", sa.Text(), nullable=False, server_default="[]"
    ),
    sa.Column("evidence_package_id", sa.String(), nullable=True),
    sa.Column("evidence_package_hash", sa.String(), nullable=True),
    sa.Column("assessment_hash", sa.String(), nullable=True),
    sa.Column("policy_package_hash", sa.String(), nullable=True),
    sa.Column("actor_hash", sa.String(), nullable=True),
    sa.Column("intent_hash", sa.String(), nullable=True),
    sa.Column("target_hash", sa.String(), nullable=True),
    sa.Column("context_hash", sa.String(), nullable=True),
    sa.Column("engine_version", sa.String(), nullable=True),
    sa.Column("input_hash", sa.String(), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("prior_decision_id", sa.String(), nullable=True),
    sa.Column("superseded_by_decision_id", sa.String(), nullable=True),
    sa.Column(
        "supersession_status",
        sa.String(),
        nullable=False,
        server_default="CURRENT",
    ),
]

_DECISION_INDEXES = [
    "evaluation_id",
    "policy_resolution_id",
    "assessment_id",
    "evidence_package_id",
    "input_hash",
    "prior_decision_id",
    "superseded_by_decision_id",
]

_AUTH_COLUMNS = [
    sa.Column("actor_id", sa.String(), nullable=True),
    sa.Column("target_id", sa.String(), nullable=True),
    sa.Column("authorized_action", sa.String(), nullable=True),
    sa.Column("authorized_parameter_constraints", sa.Text(), nullable=True),
    sa.Column("max_amount_minor", sa.BigInteger(), nullable=True),
    sa.Column("max_amount_currency", sa.String(), nullable=True),
    sa.Column("permitted_execution_system", sa.String(), nullable=True),
    sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("nonce", sa.String(), nullable=True),
    sa.Column("idempotency_key", sa.String(), nullable=True),
    sa.Column(
        "one_time_use", sa.Boolean(), nullable=False, server_default=sa.true()
    ),
    sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revocation_reason", sa.String(), nullable=True),
    sa.Column("policy_package_hash", sa.String(), nullable=True),
    sa.Column("assessment_hash", sa.String(), nullable=True),
    sa.Column("evidence_package_hash", sa.String(), nullable=True),
    sa.Column("decision_hash", sa.String(), nullable=True),
    sa.Column("signer_key_id", sa.String(), nullable=True),
    sa.Column("signature", sa.Text(), nullable=True),
    sa.Column("authorization_hash", sa.String(), nullable=True),
]

_AUTH_INDEXES = [
    "actor_id",
    "target_id",
    "nonce",
    "idempotency_key",
    "authorization_hash",
]


def upgrade() -> None:
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        for column in _DECISION_COLUMNS:
            batch_op.add_column(column)
        for column_name in _DECISION_INDEXES:
            batch_op.create_index(
                batch_op.f(f"ix_decisions_{column_name}"),
                [column_name],
                unique=False,
            )

    with op.batch_alter_table(
        "execution_authorizations", schema=None
    ) as batch_op:
        for column in _AUTH_COLUMNS:
            batch_op.add_column(column)
        for column_name in _AUTH_INDEXES:
            batch_op.create_index(
                batch_op.f(f"ix_execution_authorizations_{column_name}"),
                [column_name],
                unique=False,
            )


def downgrade() -> None:
    with op.batch_alter_table(
        "execution_authorizations", schema=None
    ) as batch_op:
        for column_name in _AUTH_INDEXES:
            batch_op.drop_index(
                batch_op.f(f"ix_execution_authorizations_{column_name}")
            )
        for column in reversed(_AUTH_COLUMNS):
            batch_op.drop_column(column.name)

    with op.batch_alter_table("decisions", schema=None) as batch_op:
        for column_name in _DECISION_INDEXES:
            batch_op.drop_index(batch_op.f(f"ix_decisions_{column_name}"))
        for column in reversed(_DECISION_COLUMNS):
            batch_op.drop_column(column.name)
