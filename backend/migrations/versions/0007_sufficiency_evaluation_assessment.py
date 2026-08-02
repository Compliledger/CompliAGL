"""evidence sufficiency, control evaluation and assessment

Revision ID: 0007_sufficiency_evaluation_assessment
Revises: 0006_control_evidence_sets
Create Date: 2026-08-02 13:00:00.000000

Adds the persistent tables backing the three deterministic runtime stages that
run after evidence collection and before the Decision stage:

* :class:`EvidenceSufficiency` — evaluates the Canonical Evidence Package
  against the EvidenceRequirementSet (per-requirement SATISFIED / PARTIAL /
  MISSING / INVALID / STALE / NOT_EVALUABLE / MANUAL_REVIEW_REQUIRED and an
  overall SUFFICIENT / PARTIAL / INSUFFICIENT / NOT_EVALUABLE /
  MANUAL_REVIEW_REQUIRED).
* :class:`ControlEvaluation` — one immutable result per applicable control,
  evaluated against normalized evidence only.
* :class:`Assessment` — the factual aggregation of the control evaluations,
  kept separate from the Decision stage.

All tables are tenant-scoped (``organization_id``) and versioned
(``schema_version``); structured fields are stored as JSON text and bound by
deterministic hash values.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007_sufficiency_evaluation_assessment"
down_revision: Union[str, None] = "0006_control_evidence_sets"
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


def _index(batch_op, table: str, column: str) -> None:
    batch_op.create_index(
        batch_op.f(f"ix_{table}_{column}"), [column], unique=False
    )


def upgrade() -> None:
    op.create_table(
        "evidence_sufficiency_results",
        *_common_columns(),
        sa.Column("evaluation_id", sa.String(), nullable=False),
        sa.Column("policy_resolution_id", sa.String(), nullable=False),
        sa.Column("evidence_requirement_set_id", sa.String(), nullable=True),
        sa.Column("canonical_evidence_package_id", sa.String(), nullable=True),
        sa.Column("collection_job_id", sa.String(), nullable=True),
        sa.Column("requirement_results", sa.Text(), nullable=False),
        sa.Column("overall_result", sa.String(), nullable=False),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("result_hash", sa.String(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table(
        "evidence_sufficiency_results", schema=None
    ) as batch_op:
        for column in (
            "organization_id",
            "evaluation_id",
            "policy_resolution_id",
            "evidence_requirement_set_id",
            "canonical_evidence_package_id",
            "collection_job_id",
            "input_hash",
            "result_hash",
        ):
            _index(batch_op, "evidence_sufficiency_results", column)

    op.create_table(
        "control_evaluations",
        *_common_columns(),
        sa.Column("evaluation_id", sa.String(), nullable=False),
        sa.Column("policy_resolution_id", sa.String(), nullable=False),
        sa.Column("applicable_control_set_id", sa.String(), nullable=True),
        sa.Column("evidence_sufficiency_id", sa.String(), nullable=True),
        sa.Column("canonical_evidence_package_id", sa.String(), nullable=True),
        sa.Column("control_evaluation_id", sa.String(), nullable=False),
        sa.Column("control_id", sa.String(), nullable=False),
        sa.Column("package_id", sa.String(), nullable=True),
        sa.Column("package_version", sa.String(), nullable=True),
        sa.Column("control_version", sa.String(), nullable=True),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("requirement_ids", sa.Text(), nullable=False),
        sa.Column("evidence_requirement_ids", sa.Text(), nullable=False),
        sa.Column("evidence_references", sa.Text(), nullable=False),
        sa.Column("evidence_sufficiency_references", sa.Text(), nullable=False),
        sa.Column("evaluation_expression", sa.Text(), nullable=True),
        sa.Column("expected_value", sa.Text(), nullable=True),
        sa.Column("observed_value", sa.Text(), nullable=True),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("result_hash", sa.String(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("control_evaluations", schema=None) as batch_op:
        for column in (
            "organization_id",
            "evaluation_id",
            "policy_resolution_id",
            "applicable_control_set_id",
            "evidence_sufficiency_id",
            "canonical_evidence_package_id",
            "control_evaluation_id",
            "control_id",
            "package_id",
            "input_hash",
            "result_hash",
        ):
            _index(batch_op, "control_evaluations", column)

    op.create_table(
        "assessments",
        *_common_columns(),
        sa.Column("evaluation_id", sa.String(), nullable=False),
        sa.Column("policy_resolution_id", sa.String(), nullable=False),
        sa.Column("applicable_control_set_id", sa.String(), nullable=True),
        sa.Column("evidence_sufficiency_id", sa.String(), nullable=True),
        sa.Column("control_evaluation_ids", sa.Text(), nullable=False),
        sa.Column("mandatory_control_summary", sa.Text(), nullable=False),
        sa.Column("evidence_sufficiency_result", sa.String(), nullable=True),
        sa.Column("overall_result", sa.String(), nullable=False),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("assessment_hash", sa.String(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("assessments", schema=None) as batch_op:
        for column in (
            "organization_id",
            "evaluation_id",
            "policy_resolution_id",
            "applicable_control_set_id",
            "evidence_sufficiency_id",
            "input_hash",
            "assessment_hash",
        ):
            _index(batch_op, "assessments", column)


def downgrade() -> None:
    op.drop_table("assessments")
    op.drop_table("control_evaluations")
    op.drop_table("evidence_sufficiency_results")
