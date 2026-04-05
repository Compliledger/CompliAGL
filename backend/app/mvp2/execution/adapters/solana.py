"""Solana execution adapter — placeholder for Solana RPC integration."""

from __future__ import annotations

from uuid import UUID

from app.mvp2.execution.adapters.base import BaseExecutionAdapter


class SolanaExecutionAdapter(BaseExecutionAdapter):
    """Adapter that submits transactions to Solana.

    .. note::

        This is a placeholder.  A production implementation would use
        ``solders`` or the Solana JSON-RPC client to build, sign, and
        broadcast transactions.
    """

    def __init__(self, rpc_url: str = "https://api.devnet.solana.com") -> None:
        self.rpc_url = rpc_url

    async def execute(
        self,
        transaction_id: UUID,
        amount: float,
        currency: str,
        metadata: dict | None = None,
    ) -> dict:
        # TODO: implement real Solana transaction submission
        return {
            "tx_hash": None,
            "status": "PENDING",
            "error": "Solana adapter not yet implemented",
        }

    async def get_status(self, tx_hash: str) -> str:
        # TODO: query Solana RPC for transaction status
        return "PENDING"
