"""PolicyResolution and ApplicabilityEvaluation request/response schemas.

These define the wire contract for the two deterministic runtime stages that
precede the decision engine:

* **Policy Resolution** — selects the governing package versions.
* **Applicability Evaluation** — evaluates each candidate requirement.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase


# --------------------------------------------------------------------------- #
# Policy Resolution
# --------------------------------------------------------------------------- #
class PolicyResolutionCreate(BaseModel):
    """Inputs for a policy-resolution run.

    The referenced actor identity and intent must already exist in the tenant.
    ``target_id`` and ``operational_context_id`` are optional; a missing context
    never silently produces approval — it surfaces as ``INDETERMINATE`` at the
    applicability stage.
    """

    organization_id: str = Field(..., min_length=1)
    actor_identity_id: str = Field(..., min_length=1)
    intent_id: str = Field(..., min_length=1)
    target_id: Optional[str] = None
    operational_context_id: Optional[str] = None


class PolicyResolutionResponse(CanonicalResponseBase):
    """Policy-resolution record as returned by the API."""

    actor_identity_id: str
    intent_id: str
    target_id: Optional[str] = None
    operational_context_id: Optional[str] = None
    status: str
    candidate_package_ids: list[Any] = Field(default_factory=list)
    selected_packages: list[Any] = Field(default_factory=list)
    conflicts: list[Any] = Field(default_factory=list)
    selection_facts: Optional[dict[str, Any]] = None
    reason_codes: list[Any] = Field(default_factory=list)
    engine_version: str
    input_hash: Optional[str] = None
    result_hash: Optional[str] = None
    resolved_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Applicability Evaluation
# --------------------------------------------------------------------------- #
class ApplicabilityEvaluationCreate(BaseModel):
    """Trigger applicability evaluation for a completed policy resolution."""

    organization_id: str = Field(..., min_length=1)
    policy_resolution_id: str = Field(..., min_length=1)


class ApplicabilityEvaluationResponse(CanonicalResponseBase):
    """A single per-requirement applicability result as returned by the API."""

    policy_resolution_id: str
    actor_identity_id: str
    intent_id: str
    target_id: Optional[str] = None
    operational_context_id: Optional[str] = None
    package_id: str
    package_version: str
    requirement_id: str
    requirement_version: Optional[str] = None
    result: str
    evaluated_expression: Optional[dict[str, Any]] = None
    observed_values: list[Any] = Field(default_factory=list)
    reason_codes: list[Any] = Field(default_factory=list)
    engine_version: str
    input_hash: Optional[str] = None
    result_hash: Optional[str] = None
    evaluated_at: Optional[datetime] = None
