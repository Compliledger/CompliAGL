"""Base adapter — abstract interface for blockchain execution backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class BaseExecutionAdapter(ABC):
    """Abstract base class for execution adapters.

    Each concrete adapter encapsulates the logic required to submit a
    transaction to a specific blockchain or settlement layer.
    """

    @abstractmethod
    async def execute(
        self,
        transaction_id: UUID,
        amount: float,
        currency: str,
        metadata: dict | None = None,
    ) -> dict:
        """Execute a transaction and return a result dict.

        Returns
        -------
        dict
            Must contain at minimum ``tx_hash`` (str | None) and
            ``status`` (str).
        """

    @abstractmethod
    async def get_status(self, tx_hash: str) -> str:
        """Return the current status of a previously submitted transaction."""
