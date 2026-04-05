"""Mock execution adapter — used for testing and local development."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.mvp2.execution.adapters.base import BaseExecutionAdapter


class MockExecutionAdapter(BaseExecutionAdapter):
    """In-memory mock adapter that simulates successful execution."""

    async def execute(
        self,
        transaction_id: UUID,
        amount: float,
        currency: str,
        metadata: dict | None = None,
    ) -> dict:
        return {
            "tx_hash": f"mock-{uuid4().hex[:16]}",
            "status": "CONFIRMED",
        }

    async def get_status(self, tx_hash: str) -> str:
        return "CONFIRMED"
