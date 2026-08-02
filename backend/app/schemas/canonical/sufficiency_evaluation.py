"""Evidence Sufficiency, Control Evaluation and Assessment schemas.

These define the wire contract for the three deterministic runtime stages that
run **after** evidence collection and **before** the Decision stage:

* **Evidence Sufficiency** — evaluates the Canonical Evidence Package against the
  EvidenceRequirementSet and produces an
  :class:`~app.models.evidence_sufficiency.EvidenceSufficiency` record.
* **Control Evaluation** — produces one immutable
  :class:`~app.models.control_evaluation.ControlEvaluation` per control.
* **Assessment** — aggregates the control evaluations into a factual
  :class:`~app.models.assessment.Assessment` (kept separate from Decision).

Structured JSON fields are returned as parsed objects so callers get the full
detail without a second round trip.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase


# --------------------------------------------------------------------------- #
# Triggers
# --------------------------------------------------------------------------- #
class ResolutionStageCreate(BaseModel):
    """Trigger a deterministic stage for a completed policy resolution."""

    organization_id: str = Field(..., min_length=1)
    policy_resolution_id: str = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# Evidence Sufficiency
# --------------------------------------------------------------------------- #
class EvidenceSufficiencyResponse(CanonicalResponseBase):
    """A persisted evidence-sufficiency record as returned by the API."""

    evaluation_id: str
    policy_resolution_id: str
    evidence_requirement_set_id: Optional[str] = None
    canonical_evidence_package_id: Optional[str] = None
    collection_job_id: Optional[str] = None
    requirement_results: list[Any] = Field(default_factory=list)
    overall_result: str
    reason_codes: list[Any] = Field(default_factory=list)
    engine_version: str
    input_hash: Optional[str] = None
    result_hash: Optional[str] = None
    evaluated_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Control Evaluation
# --------------------------------------------------------------------------- #
class ControlEvaluationResponse(CanonicalResponseBase):
    """A persisted, immutable control-evaluation result."""

    evaluation_id: str
    policy_resolution_id: str
    applicable_control_set_id: Optional[str] = None
    evidence_sufficiency_id: Optional[str] = None
    canonical_evidence_package_id: Optional[str] = None
    control_evaluation_id: str
    control_id: str
    package_id: Optional[str] = None
    package_version: Optional[str] = None
    control_version: Optional[str] = None
    mandatory: bool
    severity: Optional[str] = None
    requirement_ids: list[Any] = Field(default_factory=list)
    evidence_requirement_ids: list[Any] = Field(default_factory=list)
    evidence_references: list[Any] = Field(default_factory=list)
    evidence_sufficiency_references: list[Any] = Field(default_factory=list)
    evaluation_expression: Optional[str] = None
    expected_value: Any = None
    observed_value: Any = None
    result: str
    reason_codes: list[Any] = Field(default_factory=list)
    engine_version: str
    input_hash: Optional[str] = None
    result_hash: Optional[str] = None
    evaluated_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Assessment
# --------------------------------------------------------------------------- #
class AssessmentResponse(CanonicalResponseBase):
    """A persisted, factual assessment (aggregation of control evaluations)."""

    evaluation_id: str
    policy_resolution_id: str
    applicable_control_set_id: Optional[str] = None
    evidence_sufficiency_id: Optional[str] = None
    control_evaluation_ids: list[Any] = Field(default_factory=list)
    mandatory_control_summary: dict[str, Any] = Field(default_factory=dict)
    evidence_sufficiency_result: Optional[str] = None
    overall_result: str
    reason_codes: list[Any] = Field(default_factory=list)
    engine_version: str
    input_hash: Optional[str] = None
    assessment_hash: Optional[str] = None
    assessed_at: Optional[datetime] = None
