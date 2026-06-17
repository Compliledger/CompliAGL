"""Tests for the x402 execution adapter."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from app.mvp2.execution.adapters.x402 import (
    FacilitatorResult,
    HttpFacilitator,
    MockFacilitator,
    PaymentFacilitator,
    X402Adapter,
    build_facilitator,
)


def _run(coro):
    """Run an async coroutine to completion (avoids extra test plugins)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Helper facilitators
# ---------------------------------------------------------------------------


class AlwaysVerifiesFacilitator(PaymentFacilitator):
    """Facilitator that records calls and always verifies."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def verify(self, payment: dict, requirements: dict) -> FacilitatorResult:
        self.calls.append(payment)
        return FacilitatorResult(verified=True, reference="settled-001")


class AlwaysRejectsFacilitator(PaymentFacilitator):
    """Facilitator that always rejects the payment."""

    async def verify(self, payment: dict, requirements: dict) -> FacilitatorResult:
        return FacilitatorResult(
            verified=False, reference=None, reason="rejected by facilitator"
        )


# ---------------------------------------------------------------------------
# Payment required
# ---------------------------------------------------------------------------


def test_payment_required_when_payment_missing():
    adapter = X402Adapter(facilitator=AlwaysVerifiesFacilitator())

    result = _run(
        adapter.execute(
            transaction_id=uuid4(),
            amount=10.0,
            currency="USDC",
            metadata={"approved": True},
        )
    )

    assert result["adapter"] == "x402"
    assert result["status"] == "PAYMENT_REQUIRED"
    assert result["payment_required"] is True
    assert result["payment_verified"] is False
    assert result["payment_reference"] is None
    assert result["execution_reference"] is None
    assert result["timestamp"]
    # Includes a description of how to pay.
    assert "accepts" in result


# ---------------------------------------------------------------------------
# Payment verified
# ---------------------------------------------------------------------------


def test_payment_verified_in_body_executes():
    facilitator = AlwaysVerifiesFacilitator()
    adapter = X402Adapter(facilitator=facilitator)

    result = _run(
        adapter.execute(
            transaction_id=uuid4(),
            amount=10.0,
            currency="USDC",
            metadata={"approved": True, "payment": {"reference": "pay-123"}},
        )
    )

    assert result["status"] == "CONFIRMED"
    assert result["payment_required"] is True
    assert result["payment_verified"] is True
    assert result["payment_reference"] == "settled-001"
    assert result["execution_reference"]
    assert facilitator.calls == [{"reference": "pay-123"}]


def test_payment_supplied_via_headers():
    adapter = X402Adapter(facilitator=MockFacilitator())

    result = _run(
        adapter.execute(
            transaction_id=uuid4(),
            amount=10.0,
            currency="USDC",
            metadata={"approved": True, "headers": {"X-PAYMENT": "header-ref-9"}},
        )
    )

    assert result["status"] == "CONFIRMED"
    assert result["payment_verified"] is True
    assert result["payment_reference"] == "header-ref-9"


# ---------------------------------------------------------------------------
# Failed payment
# ---------------------------------------------------------------------------


def test_failed_payment_does_not_execute():
    adapter = X402Adapter(facilitator=AlwaysRejectsFacilitator())

    result = _run(
        adapter.execute(
            transaction_id=uuid4(),
            amount=10.0,
            currency="USDC",
            metadata={"approved": True, "payment": {"reference": "pay-bad"}},
        )
    )

    assert result["status"] == "FAILED"
    assert result["payment_required"] is True
    assert result["payment_verified"] is False
    assert result["execution_reference"] is None
    assert result["error"] == "rejected by facilitator"


def test_mock_facilitator_rejects_payment_without_reference():
    adapter = X402Adapter(facilitator=MockFacilitator())

    result = _run(
        adapter.execute(
            transaction_id=uuid4(),
            amount=10.0,
            currency="USDC",
            metadata={"approved": True, "payment": {"amount": 10.0}},
        )
    )

    # A payment object that carries no reference fails verification.
    assert result["status"] == "FAILED"
    assert result["payment_required"] is True
    assert result["payment_verified"] is False


# ---------------------------------------------------------------------------
# Approved action executes only after payment verification
# ---------------------------------------------------------------------------


def test_unapproved_action_never_executes():
    facilitator = AlwaysVerifiesFacilitator()
    adapter = X402Adapter(facilitator=facilitator)

    result = _run(
        adapter.execute(
            transaction_id=uuid4(),
            amount=10.0,
            currency="USDC",
            metadata={"approved": False, "payment": {"reference": "pay-123"}},
        )
    )

    assert result["status"] == "FAILED"
    assert result["payment_required"] is False
    assert result["payment_verified"] is False
    assert result["execution_reference"] is None
    # Facilitator must not even be consulted for an unapproved action.
    assert facilitator.calls == []


def test_execution_reference_only_set_after_verification():
    facilitator = AlwaysVerifiesFacilitator()
    adapter = X402Adapter(facilitator=facilitator)
    metadata = {"approved": True}

    # First call without payment → no execution.
    first = _run(
        adapter.execute(
            transaction_id=uuid4(), amount=1.0, currency="USDC", metadata=metadata
        )
    )
    assert first["execution_reference"] is None
    assert facilitator.calls == []

    # Second call with a verifiable payment → executes.
    metadata["payment"] = {"reference": "pay-456"}
    second = _run(
        adapter.execute(
            transaction_id=uuid4(), amount=1.0, currency="USDC", metadata=metadata
        )
    )
    assert second["payment_verified"] is True
    assert second["execution_reference"]
    assert len(facilitator.calls) == 1


# ---------------------------------------------------------------------------
# Facilitator selection
# ---------------------------------------------------------------------------


def test_build_facilitator_defaults_to_mock():
    assert isinstance(build_facilitator(""), MockFacilitator)
    assert isinstance(build_facilitator("mock"), MockFacilitator)


def test_build_facilitator_uses_http_when_configured():
    facilitator = build_facilitator("https://facilitator.example.com")
    assert isinstance(facilitator, HttpFacilitator)
