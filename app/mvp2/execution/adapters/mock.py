"""Mock execution adapter — used for testing and local development."""

from __future__ import annotations

from uuid import uuid4

from app.mvp2.execution.adapters.base import ExecutionAdapter
from app.mvp2.schemas.transaction import ExecutionResult, TransactionRequest


class MockAdapter(ExecutionAdapter):
    """In-memory mock adapter that simulates successful execution."""

    async def execute(self, transaction: TransactionRequest) -> ExecutionResult:
        return ExecutionResult(
            execution_status="CONFIRMED",
            tx_hash=f"mock-{uuid4().hex[:16]}",
            chain=transaction.chain,
            outcome="executed_mock",
        )
