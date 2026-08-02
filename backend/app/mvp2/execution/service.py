"""Execution service — dispatches an *authorized* action to an execution adapter.

Execution semantics (canonical CompliAGL boundary)
--------------------------------------------------
CompliAGL does **not** perform the underlying action. Governance produces a
decision and issues an execution *authorization*; an **external system**
performs the execution and returns a result, which CompliAGL then validates and
records. The adapters in :mod:`app.mvp2.execution.adapters` are thin bridges to
those external systems.

x402 is **one optional adapter** among several, not the definition of the
runtime — adapters are discovered lazily so the service imports and runs even
when an optional adapter (or its dependencies) is unavailable.
"""

from __future__ import annotations

from app.mvp2.execution.adapters.base import BaseExecutionAdapter
from app.mvp2.execution.adapters.mock import MockExecutionAdapter
from app.mvp2.execution.adapters.solana import SolanaExecutionAdapter
from app.mvp2.schemas.execution import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
)

# Always-available adapters.
_ADAPTER_REGISTRY: dict[str, type[BaseExecutionAdapter]] = {
    "mock": MockExecutionAdapter,
    "solana": SolanaExecutionAdapter,
}


def _register_optional_adapters() -> None:
    """Register optional adapters (e.g. x402) if importable.

    Keeping these out of the module-level imports makes x402 an *optional*
    integration: the execution runtime does not depend on it.
    """
    try:
        from app.mvp2.execution.adapters.x402 import X402Adapter

        _ADAPTER_REGISTRY.setdefault("x402", X402Adapter)
    except Exception:  # pragma: no cover - defensive optional import
        pass


_register_optional_adapters()


def available_adapters() -> list[str]:
    """Return the names of all registered execution adapters."""
    return sorted(_ADAPTER_REGISTRY)


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


async def execute_authorized_action(request: ExecutionRequest) -> ExecutionResponse:
    """Bridge an authorized action to the external execution adapter.

    The real ``amount`` and ``currency`` from the request are passed through —
    there is **no** silent substitution of zero amounts or default currencies.
    Whatever result the external adapter returns is validated and recorded.
    """
    adapter = get_adapter(request.adapter)
    result = await adapter.execute(
        transaction_id=request.transaction_id,
        amount=request.amount,
        currency=request.currency,
        metadata=request.metadata,
    )
    return _record_result(request, result)


def _record_result(request: ExecutionRequest, result: dict) -> ExecutionResponse:
    """Validate and record an external execution result."""
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


# Backwards-compatible alias (deprecated name).
execute_transaction = execute_authorized_action
