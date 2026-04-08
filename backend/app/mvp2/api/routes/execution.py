"""MVP 2 execution routes.

Provides the execute endpoint that evaluates a transaction against
governance policy, executes it through the configured adapter, and
returns the combined result.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.mvp2.execution.service import execute_transaction
from app.mvp2.schemas.execution import ExecutionRequest, ExecutionResponse

router = APIRouter(prefix="/api/mvp2", tags=["mvp2-execution"])


@router.post("/execute", response_model=ExecutionResponse)
async def execute(request: ExecutionRequest) -> ExecutionResponse:
    """Submit a transaction for execution through the configured adapter."""
    return await execute_transaction(request)
