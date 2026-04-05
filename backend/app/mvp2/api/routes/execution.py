"""MVP 2 execution routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.mvp2.execution.service import execute_transaction
from app.mvp2.schemas.execution import ExecutionRequest, ExecutionResponse

router = APIRouter(prefix="/executions", tags=["mvp2-executions"])


@router.post("/", response_model=ExecutionResponse)
async def create_execution(request: ExecutionRequest) -> ExecutionResponse:
    """Submit a transaction for execution through the configured adapter."""
    return await execute_transaction(request)
