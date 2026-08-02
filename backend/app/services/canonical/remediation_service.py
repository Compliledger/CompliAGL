"""Remediation plan service.

A :class:`RemediationPlan` is the governance-owned plan to resolve a
:class:`Finding`. A plan can only be created for a finding that is eligible for
remediation (a terminal, ineligible finding — e.g. a policy prohibition — can
never be planned). Marking a plan ``REMEDIATION_COMPLETE`` is explicitly **not**
proof of resolution; a plan only reaches ``VALIDATED`` through validated
resolution evidence.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.remediation_plan import RemediationPlan
from app.repositories.canonical import (
    FindingRepository,
    RemediationPlanRepository,
)
from app.schemas.canonical.remediation import (
    RemediationPlanCreate,
)
from app.services.canonical.errors import ConflictError, NotFoundError
from app.utils.canonical_enums import (
    FindingStatus,
    RemediationEligibility,
    RemediationPlanStatus,
)
from app.utils.hashing import hash_dict


# Terminal statuses a plan may not transition away from.
_TERMINAL_PLAN_STATES = {
    RemediationPlanStatus.VALIDATED.value,
    RemediationPlanStatus.CANCELLED.value,
}


def create_plan(db: Session, payload: RemediationPlanCreate) -> RemediationPlan:
    """Create a remediation plan for an eligible finding."""
    org = payload.organization_id
    finding = FindingRepository(db).get(org, payload.finding_id)
    if finding is None:
        raise NotFoundError(f"Finding not found: {payload.finding_id}")

    if (
        finding.terminal
        or finding.remediation_eligibility == RemediationEligibility.INELIGIBLE.value
    ):
        raise ConflictError(
            "Finding is not eligible for remediation "
            f"({finding.finding_id} is {finding.remediation_eligibility}"
            f"{' / terminal' if finding.terminal else ''})."
        )

    actions = [a.model_dump() for a in payload.remediation_actions]
    required_evidence = [
        e.model_dump() for e in payload.required_resolution_evidence
    ]
    dependencies = list(payload.dependencies)

    plan_identity = {
        "organization_id": org,
        "finding_id": payload.finding_id,
        "required_corrective_state": payload.required_corrective_state,
        "remediation_actions": actions,
        "required_resolution_evidence": required_evidence,
        "dependencies": dependencies,
    }
    plan_id = "RMP-" + hash_dict(plan_identity)[:16]

    obj = RemediationPlan(
        organization_id=org,
        remediation_plan_id=plan_id,
        finding_id=payload.finding_id,
        required_corrective_state=payload.required_corrective_state,
        remediation_actions=json.dumps(actions),
        required_resolution_evidence=json.dumps(required_evidence),
        owner=payload.owner or finding.owner,
        priority=payload.priority.value,
        due_date=payload.due_date or finding.due_date,
        dependencies=json.dumps(dependencies),
        status=RemediationPlanStatus.OPEN.value,
        plan_hash=hash_dict(plan_identity),
    )
    plan = RemediationPlanRepository(db).add(obj)

    # A finding with an active plan moves into remediation (unless already
    # further along).
    if finding.status in {FindingStatus.OPEN.value, FindingStatus.ASSIGNED.value}:
        finding.status = FindingStatus.IN_PROGRESS.value
        if payload.owner:
            finding.owner = payload.owner
        FindingRepository(db).save(finding)

    return plan


def update_status(
    db: Session,
    organization_id: str,
    resource_id: str,
    new_status: RemediationPlanStatus,
) -> Optional[RemediationPlan]:
    """Update the workflow status of a remediation plan.

    ``REMEDIATION_COMPLETE`` is accepted but never closes the finding — that
    requires validated resolution evidence.
    """
    repo = RemediationPlanRepository(db)
    plan = repo.get(organization_id, resource_id)
    if plan is None:
        return None
    if plan.status in _TERMINAL_PLAN_STATES:
        raise ConflictError(
            f"Remediation plan is in a terminal state ({plan.status}); it cannot "
            f"transition to {new_status.value}."
        )
    plan.status = new_status.value
    plan = repo.save(plan)

    finding = FindingRepository(db).get(organization_id, plan.finding_id)
    if finding is not None:
        if (
            new_status == RemediationPlanStatus.BLOCKED
            and finding.status != FindingStatus.CLOSED.value
        ):
            finding.status = FindingStatus.BLOCKED.value
            FindingRepository(db).save(finding)
        elif (
            new_status
            in {
                RemediationPlanStatus.IN_PROGRESS,
                RemediationPlanStatus.DISPATCHED,
            }
            and finding.status
            in {
                FindingStatus.OPEN.value,
                FindingStatus.ASSIGNED.value,
                FindingStatus.BLOCKED.value,
            }
        ):
            finding.status = FindingStatus.IN_PROGRESS.value
            FindingRepository(db).save(finding)
    return plan


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[RemediationPlan]:
    return RemediationPlanRepository(db).get(organization_id, resource_id)


def list_for_finding(
    db: Session, organization_id: str, finding_id: str
) -> Sequence[RemediationPlan]:
    return RemediationPlanRepository(db).list_for_finding(organization_id, finding_id)


def latest_for_finding(
    db: Session, organization_id: str, finding_id: str
) -> Optional[RemediationPlan]:
    return RemediationPlanRepository(db).latest_for_finding(organization_id, finding_id)
