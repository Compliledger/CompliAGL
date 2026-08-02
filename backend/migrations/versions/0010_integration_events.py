"""integration event outbox + delivery state (ProofSync / AuditSync / RegSync)

Revision ID: 0010_integration_events
Revises: 0009_finding_remediation
Create Date: 2026-08-02 15:30:00.000000

Adds the persistent transactional-outbox tables backing the ProofSync, AuditSync
and RegSync integration contracts and event feeds:

* ``integration_events`` — the canonical outbox record for a governance /
  assurance event. It carries references, non-sensitive attributes and digests
  of sensitive fields only (never raw sensitive evidence), keeping
  CompliAGL/CompliLedger the canonical proof source.
* ``event_deliveries`` — the per-channel, signed, authorized-projection delivery
  state with retry and dead-letter status.

Every table is tenant-scoped (``organization_id``) and versioned
(``schema_version``).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010_integration_events"
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
    # --- integration_events (outbox) --------------------------------------- #
    op.create_table(
        "integration_events",
        *_common_columns(),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("aggregate_type", sa.String(), nullable=False),
        sa.Column("aggregate_id", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("references", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("attributes", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "sensitive_digest", sa.Text(), nullable=False, server_default="{}"
        ),
        sa.Column("payload_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("integration_events", schema=None) as batch_op:
        for column in (
            "organization_id",
            "event_id",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "payload_hash",
        ):
            _create_index(batch_op, "integration_events", column)

    # --- event_deliveries (per-channel delivery state) --------------------- #
    op.create_table(
        "event_deliveries",
        *_common_columns(),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("integration_event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("adapter", sa.String(), nullable=True),
        sa.Column("projection", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("projection_hash", sa.String(), nullable=True),
        sa.Column("signer_key_id", sa.String(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="PENDING"
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "max_attempts", sa.Integer(), nullable=False, server_default="5"
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.String(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("event_deliveries", schema=None) as batch_op:
        for column in (
            "organization_id",
            "event_id",
            "integration_event_id",
            "event_type",
            "channel",
            "projection_hash",
            "external_reference",
        ):
            _create_index(batch_op, "event_deliveries", column)


def downgrade() -> None:
    op.drop_table("event_deliveries")
    op.drop_table("integration_events")
