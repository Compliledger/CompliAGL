"""x402 execution adapter — payment-gated autonomous action execution.

This adapter implements the `x402 <https://www.x402.org/>`_ "HTTP 402
Payment Required" flow for the MVP 2 execution layer.  An approved
autonomous action is only executed *after* an associated payment has been
verified through a configurable facilitator.

Flow
----
1. The adapter receives an approved action together with optional payment
   metadata (supplied in the request body or via headers).
2. If no payment is supplied, a ``402``-style *payment required* response
   is returned describing how to pay (recipient, price, network,
   facilitator).
3. If a payment is supplied, it is verified through the configured
   facilitator abstraction.  Only on successful verification is the
   underlying action executed.

For local development a built-in :class:`MockFacilitator` is used whenever
``X402_FACILITATOR_URL`` is unset (or set to ``"mock"``), so no external
services or secrets are required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.config import settings
from app.mvp2.execution.adapters.base import BaseExecutionAdapter

# Status strings returned in the structured execution result.  ``CONFIRMED``
# and ``FAILED`` map directly onto :class:`ExecutionStatus`; ``PAYMENT_REQUIRED``
# is also represented there so the execution service can surface it.
STATUS_PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
STATUS_CONFIRMED = "CONFIRMED"
STATUS_FAILED = "FAILED"


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Facilitator abstraction
# ---------------------------------------------------------------------------


class FacilitatorResult:
    """Outcome of a facilitator payment verification."""

    def __init__(
        self,
        verified: bool,
        reference: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.verified = verified
        self.reference = reference
        self.reason = reason


class PaymentFacilitator(ABC):
    """Abstract facilitator that verifies x402 payments.

    Concrete implementations talk to an external settlement/verification
    service.  The abstraction keeps the adapter decoupled from any single
    provider and allows a mock implementation for local development.
    """

    @abstractmethod
    async def verify(self, payment: dict, requirements: dict) -> FacilitatorResult:
        """Verify *payment* against the payment *requirements*."""


class MockFacilitator(PaymentFacilitator):
    """In-memory facilitator used for local development and testing.

    A payment is considered valid when it carries a non-empty reference.
    No network calls are made and no secrets are required.
    """

    async def verify(self, payment: dict, requirements: dict) -> FacilitatorResult:
        reference = _extract_reference(payment)
        if not reference:
            return FacilitatorResult(
                verified=False,
                reason="Payment reference missing",
            )
        # Allow tests / callers to simulate a rejected payment explicitly.
        if payment.get("verified") is False or payment.get("status") in {
            "FAILED",
            "REJECTED",
            "INVALID",
        }:
            return FacilitatorResult(
                verified=False,
                reference=reference,
                reason="Payment rejected by facilitator",
            )
        return FacilitatorResult(verified=True, reference=reference)


class HttpFacilitator(PaymentFacilitator):
    """Facilitator that verifies payments via an HTTP facilitator service.

    The facilitator endpoint is expected to accept a JSON body describing
    the payment and requirements and to respond with a JSON object
    containing a truthy ``verified``/``valid`` field and an optional
    settlement ``reference``/``txHash``.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def verify(self, payment: dict, requirements: dict) -> FacilitatorResult:
        try:
            import httpx
        except ImportError:  # pragma: no cover - optional dependency
            return FacilitatorResult(
                verified=False,
                reason="httpx is required for HTTP facilitator verification",
            )

        url = f"{self.base_url}/verify"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={"payment": payment, "requirements": requirements},
                )
        except Exception as exc:  # pragma: no cover - network errors
            return FacilitatorResult(
                verified=False,
                reason=f"Facilitator request failed: {exc}",
            )

        if response.status_code != 200:
            return FacilitatorResult(
                verified=False,
                reason=f"Facilitator returned status {response.status_code}",
            )

        data = response.json()
        verified = bool(data.get("verified") or data.get("valid"))
        reference = (
            data.get("reference")
            or data.get("txHash")
            or _extract_reference(payment)
        )
        reason = None if verified else data.get("reason", "Payment not verified")
        return FacilitatorResult(verified=verified, reference=reference, reason=reason)


def build_facilitator(facilitator_url: str | None = None) -> PaymentFacilitator:
    """Return a facilitator instance based on configuration.

    An explicitly supplied *facilitator_url* always takes precedence. When
    no URL is supplied, the facilitator is resolved from configuration:
    mock mode (``X402_MOCK_MODE``), an empty/``"mock"`` URL all select the
    built-in :class:`MockFacilitator`, keeping local development and the
    Compli402 demo self-contained.
    """
    if facilitator_url is None:
        if getattr(settings, "X402_MOCK_MODE", False):
            return MockFacilitator()
        facilitator_url = settings.X402_FACILITATOR_URL
    if not facilitator_url or facilitator_url.strip().lower() == "mock":
        return MockFacilitator()
    return HttpFacilitator(facilitator_url)


# ---------------------------------------------------------------------------
# Payment extraction helpers
# ---------------------------------------------------------------------------

_PAYMENT_HEADER_KEYS = ("x-payment", "x-payment-reference", "payment")


def _extract_reference(payment: dict) -> str | None:
    """Pull a settlement reference out of a payment payload."""
    if not isinstance(payment, dict):
        return None
    for key in ("reference", "tx_hash", "txHash", "transaction_hash", "id"):
        value = payment.get(key)
        if value:
            return str(value)
    return None


def _extract_payment(metadata: dict | None) -> dict | None:
    """Extract payment metadata from the request body or headers.

    Body payments are read from ``metadata["payment"]``.  Header payments
    are read from ``metadata["headers"]`` using common x402 header names.
    A header value may be a plain reference string or a JSON-like dict.
    """
    if not metadata:
        return None

    # 1. Body payment.
    body_payment = metadata.get("payment")
    if isinstance(body_payment, dict) and body_payment:
        return body_payment
    if isinstance(body_payment, str) and body_payment:
        return {"reference": body_payment}

    # 2. Header payment.
    headers = metadata.get("headers") or {}
    if isinstance(headers, dict):
        normalised = {str(k).lower(): v for k, v in headers.items()}
        for key in _PAYMENT_HEADER_KEYS:
            value = normalised.get(key)
            if isinstance(value, dict) and value:
                return value
            if isinstance(value, str) and value:
                return {"reference": value}

    return None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class X402Adapter(BaseExecutionAdapter):
    """Execution adapter implementing the x402 payment-required flow.

    Parameters
    ----------
    facilitator:
        Optional facilitator override.  When omitted, one is built from
        configuration via :func:`build_facilitator` (mock by default).
    """

    name = "x402"

    def __init__(self, facilitator: PaymentFacilitator | None = None) -> None:
        self.facilitator = facilitator or build_facilitator()
        self.recipient_address = settings.X402_RECIPIENT_ADDRESS
        self.price_usdc = settings.X402_PRICE_USDC
        self.network = settings.X402_NETWORK

    def _payment_requirements(self) -> dict:
        """Describe how an action should be paid for."""
        return {
            "recipient": self.recipient_address,
            "price_usdc": self.price_usdc,
            "network": self.network,
            "facilitator": settings.X402_FACILITATOR_URL or "mock",
        }

    def _result(
        self,
        *,
        status: str,
        payment_required: bool,
        payment_verified: bool,
        payment_reference: str | None = None,
        execution_reference: str | None = None,
        error: str | None = None,
        extra: dict | None = None,
    ) -> dict:
        """Build the structured execution result dict."""
        result = {
            "adapter": self.name,
            "status": status,
            "payment_required": payment_required,
            "payment_verified": payment_verified,
            "payment_reference": payment_reference,
            "execution_reference": execution_reference,
            # Facilitator / network / amount describe the x402 payment context
            # and round out the fields the Compli402 API surfaces.
            "facilitator": settings.X402_FACILITATOR_URL or "mock",
            "network": self.network,
            "amount": self.price_usdc,
            "timestamp": _utc_now_iso(),
            # ``tx_hash`` keeps the result compatible with the generic
            # execution service, which reads ``tx_hash``/``status``.
            "tx_hash": execution_reference,
        }
        if error is not None:
            result["error"] = error
        if extra:
            result.update(extra)
        return result

    async def execute(
        self,
        transaction_id: UUID,
        amount: float,
        currency: str,
        metadata: dict | None = None,
    ) -> dict:
        """Execute an approved action gated by an x402 payment.

        The action is only executed once payment has been verified.  When
        no payment is present a ``402``-style payment-required result is
        returned instead.
        """
        metadata = metadata or {}

        # An action must be approved before any execution is attempted.
        approved = metadata.get("approved", True)
        if not approved:
            return self._result(
                status=STATUS_FAILED,
                payment_required=False,
                payment_verified=False,
                error="Action is not approved for execution",
            )

        payment = _extract_payment(metadata)

        # No payment supplied → 402 Payment Required.
        if payment is None:
            return self._result(
                status=STATUS_PAYMENT_REQUIRED,
                payment_required=True,
                payment_verified=False,
                extra={"accepts": self._payment_requirements()},
            )

        # Verify the supplied payment through the facilitator abstraction.
        verification = await self.facilitator.verify(
            payment, self._payment_requirements()
        )
        if not verification.verified:
            return self._result(
                status=STATUS_FAILED,
                payment_required=True,
                payment_verified=False,
                payment_reference=verification.reference,
                error=verification.reason or "Payment verification failed",
            )

        # Payment verified → execute the approved autonomous action.
        execution_reference = f"x402-{uuid4().hex[:16]}"
        return self._result(
            status=STATUS_CONFIRMED,
            payment_required=True,
            payment_verified=True,
            payment_reference=verification.reference,
            execution_reference=execution_reference,
        )

    async def get_status(self, tx_hash: str) -> str:
        """Return the status of a previously executed action.

        The x402 adapter executes synchronously, so a known execution
        reference is always considered ``CONFIRMED``.
        """
        return STATUS_CONFIRMED if tx_hash else STATUS_FAILED
