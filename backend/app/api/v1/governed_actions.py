"""Governed-action route -- thin wrapper over ``governed_action_service.propose``.

Validates input and delegates to the existing canonical intent -> decision
pipeline; contains no decision logic itself (docs/dev-rules.md rule 3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.governed_action import (
    GovernedActionProposeRequest,
    GovernedActionResponse,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import governed_action_service
from app.utils.canonical_enums import IntentType

router = APIRouter(tags=["v1:governed-actions"])


@router.post(
    "/governed-actions", response_model=GovernedActionResponse, status_code=201
)
def propose_governed_action(
    payload: GovernedActionProposeRequest,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Propose a governed treasury action and return the resulting decision."""
    result = governed_action_service.propose(
        db,
        organization_id,
        actor_id=payload.actor_id,
        intent_type=IntentType.TRANSFER,
        action=payload.action,
        compliidentity_resource="circle.treasury_action",
        compliidentity_action="propose",
        resource_instance=payload.target_identifier,
        target_identifier=payload.target_identifier,
        rationale=payload.rationale,
        amount_minor=payload.amount_minor,
        amount_currency=payload.amount_currency,
        extra_parameters={"asset": payload.asset, "network": payload.network},
        correlation_id=payload.correlation_id,
    )
    decision = orm_to_dict(result.decision)
    return GovernedActionResponse(
        intent_id=result.intent.id,
        policy_resolution_id=result.policy_resolution.id,
        assessment_id=result.assessment.id if result.assessment is not None else None,
        decision_id=result.decision.id,
        outcome=decision["outcome"],
        reason_codes=decision.get("reason_codes") or [],
        decision_conditions_triggered=decision.get("decision_conditions_triggered")
        or [],
        decision_hash=decision.get("decision_hash"),
        assessment_hash=decision.get("assessment_hash"),
        evidence_package_hash=decision.get("evidence_package_hash"),
        policy_package_hash=decision.get("policy_package_hash"),
    )
