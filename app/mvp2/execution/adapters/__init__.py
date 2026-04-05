"""Execution adapters for CompliAGL MVP 2."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.mvp2.schemas.transaction import ExecutionResult


class ExecutionAdapter(ABC):
    """Abstract base class for chain execution adapters.

    Each concrete adapter encapsulates the logic required to submit a
    transaction to a specific blockchain or settlement layer and return
    an :class:`ExecutionResult`.
    """

    @abstractmethod
    def execute(self, transaction_id: str, **kwargs) -> ExecutionResult:
        """Execute a transaction and return an :class:`ExecutionResult`."""
"""MVP 2 execution adapters — pluggable blockchain backends."""
