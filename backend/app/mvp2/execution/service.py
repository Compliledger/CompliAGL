"""Execution service — dispatches transactions to the appropriate adapter."""

from __future__ import annotations

from app.mvp2.execution.adapters.base import BaseExecutionAdapter
from app.mvp2.execution.adapters.mock import MockExecutionAdapter
from app.mvp2.execution.adapters.solana import SolanaExecutionAdapter
from app.mvp2.schemas.execution import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
)

# Registry of available adapters keyed by name.
_ADAPTER_REGISTRY: dict[str, type[BaseExecutionAdapter]] = {
    "mock": MockExecutionAdapter,
    "solana": SolanaExecutionAdapter,
}


def get_adapter(name: str) -> BaseExecutionAdapter:
    """Return an instantiated adapter by name.

    Raises
    ------
    ValueError
        If the adapter name is not registered.
    """
    adapter_cls = _ADAPTER_REGISTRY.get(name)
    if adapter_cls is None:
        raise ValueError(f"Unknown execution adapter: {name!r}")
    return adapter_cls()


async def execute_transaction(request: ExecutionRequest) -> ExecutionResponse:
    """Execute a transaction through the requested adapter."""
    adapter = get_adapter(request.adapter)
    result = await adapter.execute(
        transaction_id=request.transaction_id,
        amount=0,  # Amount would come from a persistent store in production
        currency="USD",
        metadata=request.metadata,
    )
    tx_hash = result.get("tx_hash")
    raw_status = result.get("status", "FAILED")
    error = result.get("error")

    try:
        status = ExecutionStatus(raw_status)
    except ValueError:
        status = ExecutionStatus.FAILED

    return ExecutionResponse(
        transaction_id=request.transaction_id,
        status=status,
        tx_hash=tx_hash,
        adapter=request.adapter,
        error=error,
        metadata=request.metadata,
    )
