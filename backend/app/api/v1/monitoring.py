"""Continuous monitoring & automated re-evaluation v1 routes.

Exposes the continuous-monitoring branch:

* submit a monitoring event,
* list monitoring events,
* inspect the impact analysis (which evaluations / records a change affects),
* trigger an automated re-evaluation,
* inspect re-evaluation status,
* retrieve the decision / proof supersession chains.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.monitoring import (
    DecisionChainResponse,
    ImpactAnalysisResponse,
    MonitoringEventResponse,
    MonitoringEventSubmit,
    ProofChainResponse,
    ReevaluationRunResponse,
    ReevaluationTriggerRequest,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical.errors import ConflictError, NotFoundError
from app.services.canonical.monitoring import (
    impact_analysis,
    monitoring_service,
    proof_supersession,
    reevaluation_job,
    supersession_service,
)

router = APIRouter(prefix="/monitoring", tags=["v1:monitoring"])


# --------------------------------------------------------------------------- #
# Monitoring events
# --------------------------------------------------------------------------- #
@router.post(
    "/events", response_model=MonitoringEventResponse, status_code=201
)
def submit_monitoring_event(
    payload: MonitoringEventSubmit, db: Session = Depends(get_db)
):
    event = monitoring_service.submit_event(
        db,
        payload.organization_id,
        change_type=payload.change_type,
        source=payload.source,
        affected_object_type=payload.affected_object_type,
        affected_object_id=payload.affected_object_id,
        old_state_hash=payload.old_state_hash,
        new_state_hash=payload.new_state_hash,
        severity=payload.severity,
        provenance=payload.provenance,
        correlation_id=payload.correlation_id,
        intent_id=payload.intent_id,
        evaluation_id=payload.evaluation_id,
        detected_at=payload.detected_at,
    )
    return orm_to_dict(event)


@router.get("/events", response_model=list[MonitoringEventResponse])
def list_monitoring_events(
    change_type: Optional[str] = None,
    affected_object_type: Optional[str] = None,
    affected_object_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    events = monitoring_service.list_(
        db,
        organization_id,
        change_type=change_type,
        affected_object_type=affected_object_type,
        affected_object_id=affected_object_id,
        correlation_id=correlation_id,
        skip=skip,
        limit=limit,
    )
    return [orm_to_dict(e) for e in events]


@router.get(
    "/events/{monitoring_event_id}", response_model=MonitoringEventResponse
)
def get_monitoring_event(
    monitoring_event_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    event = monitoring_service.get(db, organization_id, monitoring_event_id)
    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"MonitoringEvent not found: {monitoring_event_id}",
        )
    return orm_to_dict(event)


# --------------------------------------------------------------------------- #
# Impact analysis (list affected evaluations + records)
# --------------------------------------------------------------------------- #
@router.get(
    "/events/{monitoring_event_id}/impact",
    response_model=ImpactAnalysisResponse,
)
def get_impact_analysis(
    monitoring_event_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    event = monitoring_service.get(db, organization_id, monitoring_event_id)
    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"MonitoringEvent not found: {monitoring_event_id}",
        )
    return impact_analysis.analyze(db, organization_id, event).to_dict()


# --------------------------------------------------------------------------- #
# Re-evaluation
# --------------------------------------------------------------------------- #
@router.post(
    "/events/{monitoring_event_id}/reevaluate",
    response_model=ReevaluationRunResponse,
    status_code=201,
)
def trigger_reevaluation(
    monitoring_event_id: str,
    payload: ReevaluationTriggerRequest | None = None,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    payload = payload or ReevaluationTriggerRequest()
    try:
        run = reevaluation_job.trigger(
            db,
            organization_id,
            monitoring_event_id,
            resulting_outcome=(
                payload.resulting_outcome.value
                if payload.resulting_outcome is not None
                else None
            ),
            reason=payload.reason,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return orm_to_dict(run)


@router.get("/reevaluations", response_model=list[ReevaluationRunResponse])
def list_reevaluations(
    status: Optional[str] = None,
    intent_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    runs = reevaluation_job.list_(
        db,
        organization_id,
        status=status,
        intent_id=intent_id,
        skip=skip,
        limit=limit,
    )
    return [orm_to_dict(r) for r in runs]


@router.get(
    "/reevaluations/{run_id}", response_model=ReevaluationRunResponse
)
def get_reevaluation(
    run_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    run = reevaluation_job.get(db, organization_id, run_id)
    if run is None:
        raise HTTPException(
            status_code=404, detail=f"ReevaluationRun not found: {run_id}"
        )
    return orm_to_dict(run)


# --------------------------------------------------------------------------- #
# Supersession chains
# --------------------------------------------------------------------------- #
@router.get(
    "/supersession/decisions/{decision_id}",
    response_model=DecisionChainResponse,
)
def get_decision_chain(
    decision_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    chain = supersession_service.decision_chain(
        db, organization_id, decision_id
    )
    if chain is None:
        raise HTTPException(
            status_code=404, detail=f"Decision not found: {decision_id}"
        )
    return chain


@router.get(
    "/supersession/proofs/{aiproof_id}", response_model=ProofChainResponse
)
def get_proof_chain(
    aiproof_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    chain = proof_supersession.proof_chain(db, organization_id, aiproof_id)
    if chain is None:
        raise HTTPException(
            status_code=404, detail=f"AIProof not found: {aiproof_id}"
        )
    return chain
