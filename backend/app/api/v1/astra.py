"""Astra agent-turn v1 route.

A thin HTTP wrapper around ``app.astra.responses.loop.run_agent_turn``. This
exists purely to expose the already-built, already-unit-tested agent loop
over HTTP for live/manual testing and for the end-to-end rehearsal -- it adds
no new authority or governance logic of its own. Tenant scoping follows the
same ``X-Organization-Id`` convention as the rest of the v1 API.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.astra.context import build_context
from app.astra.errors import AstraError, AstraNotConfiguredError
from app.astra.personas import persona_names
from app.astra.responses.loop import run_agent_turn
from app.core.database import get_db

router = APIRouter(prefix="/astra", tags=["v1:astra"])


class AstraTurnRequest(BaseModel):
    case_id: str
    user_message: str
    actor_id: Optional[str] = None
    correlation_id: Optional[str] = None


class AstraTurnResponse(BaseModel):
    stopped: str
    final_text: Optional[str] = None
    decision: Optional[dict[str, Any]] = None
    invocations: list[dict[str, Any]]
    iterations: int


@router.post("/{persona}/turn", response_model=AstraTurnResponse)
def run_turn(
    persona: str,
    payload: AstraTurnRequest,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    persona_key = persona.strip().upper()
    if persona_key not in persona_names():
        raise HTTPException(
            status_code=404,
            detail=f"Unknown persona {persona!r}; expected one of {sorted(persona_names())}",
        )

    ctx = build_context(
        db,
        organization_id=organization_id,
        persona_name=persona_key,
        case_id=payload.case_id,
        actor_id=payload.actor_id,
        correlation_id=payload.correlation_id,
    )

    try:
        result = run_agent_turn(ctx, user_message=payload.user_message)
    except AstraNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AstraError as exc:
        raise HTTPException(status_code=502, detail=f"Astra invocation failed: {exc}")
    except Exception as exc:  # noqa: BLE001 -- surface auth/network errors, don't 500 opaquely
        raise HTTPException(
            status_code=502,
            detail=f"Astra invocation failed ({type(exc).__name__}): {exc}",
        )

    return AstraTurnResponse(
        stopped=result.stopped,
        final_text=result.final_text,
        decision=result.decision,
        invocations=[asdict(inv) for inv in result.invocations],
        iterations=result.iterations,
    )