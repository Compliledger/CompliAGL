"""EvidenceOrchestrationPlan ORM model.

An **EvidenceOrchestrationPlan** is the deterministic plan built from an
:class:`~app.models.evidence_requirement_set.EvidenceRequirementSet`. For every
resolved, required/conditional evidence requirement it records which
authoritative connector was selected, the collection task parameters (subject,
target, timeout, retry policy) and — crucially — which requirements have **no**
authoritative connector and are therefore ``UNRESOLVED``. A missing connector is
never silently ignored; it surfaces in ``unresolved``.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class EvidenceOrchestrationPlan(CanonicalMixin, Base):
    """Deterministic plan selecting connectors for evidence requirements."""

    __tablename__ = "evidence_orchestration_plans"

    policy_resolution_id = Column(String, nullable=False, index=True)
    evidence_requirement_set_id = Column(String, nullable=False, index=True)
    actor_identity_id = Column(String, nullable=True, index=True)
    intent_id = Column(String, nullable=True, index=True)
    target_id = Column(String, nullable=True, index=True)
    operational_context_id = Column(String, nullable=True, index=True)

    # Whether this plan is scoped to run in production mode (mock connectors
    # rejected). Stored so a job inherits the plan's mode.
    production_mode = Column(String, nullable=False, default="false")

    # JSON list of collection tasks (one per resolved requirement).
    tasks = Column(Text, nullable=False, default="[]")
    # JSON list of requirements with no authoritative connector.
    unresolved = Column(Text, nullable=False, default="[]")
    reason_codes = Column(Text, nullable=False, default="[]")

    engine_version = Column(String, nullable=False)
    plan_hash = Column(String, nullable=True, index=True)
    planned_at = Column(DateTime(timezone=True), nullable=True)
