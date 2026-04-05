"""Solana execution adapter — placeholder for Solana RPC integration."""

from __future__ import annotations

from app.mvp2.execution.adapters.base import ExecutionAdapter
from app.mvp2.schemas.transaction import ExecutionResult, TransactionRequest


class SolanaAdapter(ExecutionAdapter):
    """Adapter that submits transactions to Solana.

    .. note::

        This is a placeholder.  A production implementation would use
        ``solders`` or the Solana JSON-RPC client to build, sign, and
        broadcast transactions.
    """

    def __init__(self, rpc_url: str = "https://api.devnet.solana.com") -> None:
        self.rpc_url = rpc_url

    async def execute(self, transaction: TransactionRequest) -> ExecutionResult:
        # TODO: implement real Solana transaction submission
        return ExecutionResult(
            execution_status="PENDING",
            tx_hash=None,
            chain="solana",
            outcome="solana_adapter_not_implemented",
        )
