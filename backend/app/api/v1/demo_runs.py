"""Demo #3 orchestration surface: derived run-state reads + a real reset.

These routes add no new governance or authority logic of their own -- they
read state other services (``governed_action_service``,
``escalation_approval_service``, ``authorization_service``, the AIProof
service) already produced, and, for reset, delete rows those same services
own. See ``app/services/canonical/demo_run_service.py`` and
``demo_reset_service.py`` for what is and is not covered.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.services.canonical import demo_reset_service, demo_run_service

router = APIRouter(tags=["v1:demo-runs"])


@router.get("/demo-runs/{correlation_id}")
def get_demo_run(
    correlation_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """The current derived run state for one correlation id.

    404 when no intent in this tenant carries that ``correlation_id`` --
    either the run never started, or the caller never set one.
    """
    view = demo_run_service.get_run_state(
        db, organization_id, correlation_id=correlation_id
    )
    if view is None:
        raise HTTPException(
            status_code=404,
            detail=f"No run found for correlation_id={correlation_id!r}",
        )
    return view


@router.get("/demo-runs")
def list_demo_runs(
    case_id: str,
    limit: int = 50,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Every distinct run (one per correlation id) recorded for one case,
    most recently started first."""
    return demo_run_service.list_run_states(
        db, organization_id, case_id=case_id, limit=limit
    )


@router.post("/demo-reset")
def reset_demo(
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Delete every per-run canonical record for this tenant.

    Leaves seeded infrastructure (the organization itself, AIRA/SENTRY/
    Jordan actor identities, published governance packages, the evidence
    connector registry) untouched -- see ``demo_reset_service`` for exactly
    what is and is not cleared.
    """
    deleted = demo_reset_service.reset_demo_state(db, organization_id)
    return {"organization_id": organization_id, "deleted": deleted}
