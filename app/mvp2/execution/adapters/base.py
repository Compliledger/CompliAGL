"""Base adapter — abstract interface for execution backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.mvp2.schemas.transaction import ExecutionResult, TransactionRequest


class ExecutionAdapter(ABC):
    """Abstract base class for execution adapters.

    Each concrete adapter (e.g. ``MockAdapter``, ``SolanaAdapter``)
    encapsulates the logic required to submit a transaction to a
    specific blockchain or settlement layer.
    """

    @abstractmethod
    async def execute(self, transaction: TransactionRequest) -> ExecutionResult:
        """Execute a transaction and return the result.

        Parameters
        ----------
        transaction:
            The fully-formed transaction request to execute.

        Returns
        -------
        ExecutionResult
            Outcome of the execution including status, optional tx hash,
            chain identifier, and human-readable outcome.
        """
