"""Control Determination and Evidence Requirement Resolution schemas.

These define the wire contract for the two deterministic runtime stages that
run **after** Applicability Evaluation and **before** evidence collection:

* **Control Determination** — selects the controls mapped to applicable /
  conditionally applicable requirements and produces an
  :class:`~app.models.applicable_control_set.ApplicableControlSet`.
* **Evidence Requirement Resolution** — resolves the evidence needed by every
  applicable control and produces an
  :class:`~app.models.evidence_requirement_set.EvidenceRequirementSet`.

The nested control / evidence entries are returned as plain dicts (already
parsed from JSON text) so callers get the full determination detail without a
second round trip.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase


# --------------------------------------------------------------------------- #
# Control Determination
# --------------------------------------------------------------------------- #
class ControlDeterminationCreate(BaseModel):
    """Trigger Control Determination for a completed policy resolution."""

    organization_id: str = Field(..., min_length=1)
    policy_resolution_id: str = Field(..., min_length=1)


class ApplicableControlSetResponse(CanonicalResponseBase):
    """A persisted set of applicable controls as returned by the API."""

    policy_resolution_id: str
    actor_identity_id: str
    intent_id: str
    target_id: Optional[str] = None
    operational_context_id: Optional[str] = None
    controls: list[Any] = Field(default_factory=list)
    reason_codes: list[Any] = Field(default_factory=list)
    engine_version: str
    input_hash: Optional[str] = None
    result_hash: Optional[str] = None
    determined_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Evidence Requirement Resolution
# --------------------------------------------------------------------------- #
class EvidenceRequirementResolutionCreate(BaseModel):
    """Trigger Evidence Requirement Resolution for a policy resolution."""

    organization_id: str = Field(..., min_length=1)
    policy_resolution_id: str = Field(..., min_length=1)


class EvidenceRequirementSetResponse(CanonicalResponseBase):
    """A persisted set of resolved evidence requirements."""

    policy_resolution_id: str
    applicable_control_set_id: str
    actor_identity_id: str
    intent_id: str
    target_id: Optional[str] = None
    operational_context_id: Optional[str] = None
    evidence_requirements: list[Any] = Field(default_factory=list)
    reason_codes: list[Any] = Field(default_factory=list)
    engine_version: str
    input_hash: Optional[str] = None
    result_hash: Optional[str] = None
    resolved_at: Optional[datetime] = None
