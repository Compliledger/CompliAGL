"""canonical first-class runtime domain objects

Revision ID: 0003_canonical_domain
Revises: 0002_add_ai_proofs
Create Date: 2026-08-02 01:00:00.000000

Adds the persistent tables for the canonical runtime sequence:
ActorIdentity, Intent, Target, OperationalContext, GovernanceEvaluation,
Decision, ExecutionAuthorization, and ExternalExecutionResult. Every table is
tenant-scoped (``organization_id``) and versioned (``schema_version``).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_canonical_domain"
down_revision: Union[str, None] = "0002_add_ai_proofs"
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


def upgrade() -> None:
    op.create_table(
        "actor_identities",
        *_common_columns(),
        sa.Column("actor_type", sa.String(), nullable=False),
        sa.Column("human_principal_id", sa.String(), nullable=True),
        sa.Column("external_account_id", sa.String(), nullable=True),
        sa.Column("wallet_or_agent_account_id", sa.String(), nullable=True),
        sa.Column("credential_type", sa.String(), nullable=False),
        sa.Column("credential_issuer", sa.String(), nullable=True),
        sa.Column("credential_reference", sa.String(), nullable=True),
        sa.Column("verification_status", sa.String(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_status", sa.String(), nullable=False),
        sa.Column("identity_metadata", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("actor_identities", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_actor_identities_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_actor_identities_external_account_id"), ["external_account_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_actor_identities_wallet_or_agent_account_id"), ["wallet_or_agent_account_id"], unique=False)

    op.create_table(
        "intents",
        *_common_columns(),
        sa.Column("intent_type", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("requested_outcome", sa.String(), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("originating_application", sa.String(), nullable=True),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("amount_currency", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("integrity_hash", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("intents", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_intents_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_intents_actor_id"), ["actor_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_intents_correlation_id"), ["correlation_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_intents_idempotency_key"), ["idempotency_key"], unique=False)
        batch_op.create_index(batch_op.f("ix_intents_integrity_hash"), ["integrity_hash"], unique=False)

    op.create_table(
        "targets",
        *_common_columns(),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("external_identifier", sa.String(), nullable=True),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("organization", sa.String(), nullable=True),
        sa.Column("classification", sa.String(), nullable=True),
        sa.Column("trust_status", sa.String(), nullable=False),
        sa.Column("network_or_environment", sa.String(), nullable=True),
        sa.Column("target_metadata", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("targets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_targets_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_targets_external_identifier"), ["external_identifier"], unique=False)

    op.create_table(
        "operational_contexts",
        *_common_columns(),
        sa.Column("business_unit", sa.String(), nullable=True),
        sa.Column("jurisdiction", sa.String(), nullable=True),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("context_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("risk_state", sa.Text(), nullable=True),
        sa.Column("account_state", sa.Text(), nullable=True),
        sa.Column("allowance_state", sa.Text(), nullable=True),
        sa.Column("merchant_state", sa.Text(), nullable=True),
        sa.Column("asset_state", sa.Text(), nullable=True),
        sa.Column("network_state", sa.Text(), nullable=True),
        sa.Column("operational_state_snapshot", sa.Text(), nullable=True),
        sa.Column("source_references", sa.Text(), nullable=True),
        sa.Column("context_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("operational_contexts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_operational_contexts_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_operational_contexts_context_hash"), ["context_hash"], unique=False)

    op.create_table(
        "governance_evaluations",
        *_common_columns(),
        sa.Column("actor_identity_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("operational_context_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("evaluation_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("governance_evaluations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_governance_evaluations_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_governance_evaluations_actor_identity_id"), ["actor_identity_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_governance_evaluations_intent_id"), ["intent_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_governance_evaluations_target_id"), ["target_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_governance_evaluations_operational_context_id"), ["operational_context_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_governance_evaluations_evaluation_hash"), ["evaluation_hash"], unique=False)

    op.create_table(
        "decisions",
        *_common_columns(),
        sa.Column("governance_evaluation_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.String(), nullable=True),
        sa.Column("decision_hash", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_decisions_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_decisions_governance_evaluation_id"), ["governance_evaluation_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_decisions_intent_id"), ["intent_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_decisions_decision_hash"), ["decision_hash"], unique=False)

    op.create_table(
        "execution_authorizations",
        *_common_columns(),
        sa.Column("decision_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("authorization_token", sa.String(), nullable=True),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("execution_authorizations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_execution_authorizations_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_execution_authorizations_decision_id"), ["decision_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_execution_authorizations_intent_id"), ["intent_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_execution_authorizations_authorization_token"), ["authorization_token"], unique=False)

    op.create_table(
        "external_execution_results",
        *_common_columns(),
        sa.Column("execution_authorization_id", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("adapter", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("external_reference", sa.String(), nullable=True),
        sa.Column("settlement_chain", sa.String(), nullable=True),
        sa.Column("result_payload", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("external_execution_results", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_external_execution_results_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_external_execution_results_execution_authorization_id"), ["execution_authorization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_external_execution_results_intent_id"), ["intent_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_external_execution_results_external_reference"), ["external_reference"], unique=False)


def downgrade() -> None:
    op.drop_table("external_execution_results")
    op.drop_table("execution_authorizations")
    op.drop_table("decisions")
    op.drop_table("governance_evaluations")
    op.drop_table("operational_contexts")
    op.drop_table("targets")
    op.drop_table("intents")
    op.drop_table("actor_identities")
