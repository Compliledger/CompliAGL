"""Execution service — dispatches approved transactions to the appropriate adapter."""

from __future__ import annotations

from app.mvp2.execution.adapters.base import ExecutionAdapter
from app.mvp2.execution.adapters.mock import MockAdapter
from app.mvp2.execution.adapters.solana import SolanaAdapter
from app.mvp2.schemas.decision import DecisionResult, DecisionStatus
from app.mvp2.schemas.transaction import ExecutionResult, TransactionRequest


def get_execution_adapter(adapter_name: str) -> ExecutionAdapter:
    """Return an instantiated execution adapter by name.

    Parameters
    ----------
    adapter_name:
        Name of the adapter.  Recognised values are ``"mock"`` and
        ``"solana"``.  Any other value falls back to ``MockAdapter``.

    Returns
    -------
    ExecutionAdapter
        A concrete adapter instance ready for use.
    """
    if adapter_name == "solana":
        return SolanaAdapter()
    return MockAdapter()


async def execute_if_approved(
    transaction: TransactionRequest,
    decision: DecisionResult,
    adapter_name: str = "mock",
) -> ExecutionResult | None:
    """Execute *transaction* only when *decision* is ``APPROVE``.

    Parameters
    ----------
    transaction:
        The transaction to execute.
    decision:
        The governance decision for this transaction.
    adapter_name:
        Which execution adapter to use (default ``"mock"``).

    Returns
    -------
    ExecutionResult | None
        The execution result if the decision is ``APPROVE``, otherwise
        ``None``.
    """
    if decision.decision != DecisionStatus.APPROVE:
        return None

    adapter = get_execution_adapter(adapter_name)
    return await adapter.execute(transaction)
