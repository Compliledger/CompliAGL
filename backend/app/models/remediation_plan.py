"""RemediationPlan ORM model — canonical first-class resource.

A **RemediationPlan** is the concrete plan to resolve a :class:`Finding`. It
describes the required corrective state, the remediation actions, the required
resolution evidence, ownership, priority, scheduling and dependencies. It is the
governance-owned plan — even when a plan is dispatched to DevSync, CompliAGL
retains the canonical remediation state and DevSync never becomes the source of
truth.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import (
    RemediationPlanStatus,
    RemediationPriority,
)


class RemediationPlan(CanonicalMixin, Base):
    """Persistent plan describing how a finding is to be remediated."""

    __tablename__ = "remediation_plans"

    remediation_plan_id = Column(String, nullable=False, index=True)
    finding_id = Column(String, nullable=False, index=True)

    # --- Plan content ---
    required_corrective_state = Column(Text, nullable=True)
    # JSON list of remediation actions, each with an id / description / owner.
    remediation_actions = Column(Text, nullable=False, default="[]")
    # JSON list of required resolution-evidence descriptors (evidence_type,
    # mandatory flag, allowed issuers, freshness threshold, ...).
    required_resolution_evidence = Column(Text, nullable=False, default="[]")

    # --- Ownership / scheduling ---
    owner = Column(String, nullable=True, index=True)
    priority = Column(
        String, nullable=False, default=RemediationPriority.MEDIUM.value
    )
    due_date = Column(DateTime(timezone=True), nullable=True)
    # JSON list of remediation_plan_id / finding_id dependencies.
    dependencies = Column(Text, nullable=False, default="[]")

    # --- Workflow state ---
    status = Column(
        String, nullable=False, default=RemediationPlanStatus.OPEN.value
    )

    # --- Determinism / provenance ---
    plan_hash = Column(String, nullable=True, index=True)
