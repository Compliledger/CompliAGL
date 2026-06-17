"""Compli402 — public, competition-ready x402 governance API.

This route layer exposes CompliAGL's governance engine combined with the
x402 "HTTP 402 Payment Required" execution flow through a small, demo-ready
public surface.

Flow
----
1. An actor submits an intent.
2. CompliAGL evaluates governance policy for that intent.
3. If the decision is ``DENIED`` → stop and return the denial.
4. If the decision is ``ESCALATED`` → return *escalation required*.
5. If the decision is ``APPROVED`` → an x402 payment is required.
6. If the payment is missing → a ``402``-style *payment required* response.
7. If the payment is verified → the approved action is executed.
8. An AIProof bundle is generated for the execution.
9. The AIProof is anchored via the shared ``compliledger-algorand-adapter``
   through :mod:`app.mvp2.anchor.algorand_adapter_service`.
10. The execution result, AIProof bundle, and Algorand anchor receipt are
    returned together.

All state (proofs) is kept in-memory — this is a demo surface.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings
from app.mvp2.anchor.algorand_adapter_service import anchor_ai_proof_bundle
from app.mvp2.core.decision_engine import evaluate
from app.mvp2.core.policy_engine import list_policies
from app.mvp2.execution.adapters.x402 import X402Adapter
from app.mvp2.identity.actors import get_actor
from app.mvp2.proof.generator import generate_proof
from app.mvp2.schemas.compli402 import (
    Compli402Decision,
    Compli402ExecuteResponse,
    Compli402Intent,
    Compli402Status,
    Compli402VerifyResponse,
)
from app.mvp2.schemas.decision import DecisionRequest, DecisionResult
from app.mvp2.schemas.proof import ProofRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compli402", tags=["compli402"])

# ---------------------------------------------------------------------------
# In-memory proof store (demo surface)
# ---------------------------------------------------------------------------
_PROOF_STORE: dict[str, dict] = {}
_PROOF_ORDER: list[str] = []


def _store_proof(proof_hash: str, bundle: dict) -> None:
    """Persist a proof bundle in-memory, tracking insertion order."""
    if proof_hash not in _PROOF_STORE:
        _PROOF_ORDER.append(proof_hash)
    _PROOF_STORE[proof_hash] = bundle


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evaluate_intent(intent: Compli402Intent) -> tuple[UUID, object]:
    """Resolve the actor, evaluate policy, and return (transaction_id, decision)."""
    actor = get_actor(intent.actor_id)
    if actor is None:
        raise HTTPException(
            status_code=404, detail=f"Actor not found: {intent.actor_id}"
        )

    transaction_id = intent.transaction_id or uuid4()
    decision_request = DecisionRequest(
        transaction_id=transaction_id,
        actor_id=intent.actor_id,
        action=intent.action,
        amount=intent.amount,
        currency=intent.currency,
        metadata=intent.metadata,
    )
    decision = evaluate(request=decision_request, policies=list_policies())
    return transaction_id, decision


def _decision_summary(decision) -> Compli402Decision:
    """Project a ``DecisionResponse`` onto the public decision summary."""
    return Compli402Decision(
        result=decision.result.value,
        reason_codes=decision.reason_codes,
        matched_policies=decision.matched_policies,
    )


def _build_aiproof(
    *,
    transaction_id: UUID,
    intent: Compli402Intent,
    decision,
    execution: dict,
) -> dict:
    """Generate and assemble the AIProof bundle for an executed intent."""
    actor = get_actor(intent.actor_id)
    proof = generate_proof(
        ProofRequest(
            transaction_id=transaction_id,
            decision_result=decision.result.value,
            reason_codes=decision.reason_codes,
            metadata={
                "action": intent.action,
                "amount": intent.amount,
                "currency": intent.currency,
                "execution_adapter": X402Adapter.name,
                "payment_reference": execution.get("payment_reference"),
            },
        )
    )

    # Fields below mirror what app.mvp2.anchor.algorand_adapter_service reads
    # when mapping an AIProof onto the shared adapter's ProofSchema.
    return {
        "proof_hash": proof.proof_hash,
        "transaction_id": str(transaction_id),
        "actor_id": str(intent.actor_id),
        "intent_id": str(transaction_id),
        "decision": decision.result.value,
        "decision_reason": decision.reason_codes,
        "reason_codes": decision.reason_codes,
        "policy_version": "mvp2",
        "created_at": _utc_now_iso(),
        "actor": (actor.model_dump(mode="json") if actor is not None else None),
        "intent": {
            "action": intent.action,
            "amount": intent.amount,
            "currency": intent.currency,
        },
        "execution_adapter": X402Adapter.name,
        "payment_reference": execution.get("payment_reference"),
        "x402_status": execution.get("status"),
        "payload": proof.payload,
        "status": proof.status.value,
    }


def _anchor_proof(aiproof: dict) -> dict:
    """Anchor the AIProof via the shared adapter, degrading gracefully.

    The shared ``compliledger-algorand-adapter`` is an optional dependency.
    When it is unavailable (or anchoring fails) a structured, non-fatal
    receipt is returned so the demo flow always completes.
    """
    try:
        return anchor_ai_proof_bundle(aiproof)
    except ImportError as exc:
        logger.warning("Algorand adapter unavailable — skipping anchor: %s", exc)
        return {
            "anchored": False,
            "chain": "algorand",
            "proof_hash": aiproof.get("proof_hash"),
            "reason": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive, network/runtime
        logger.exception("Anchoring AIProof failed")
        return {
            "anchored": False,
            "chain": "algorand",
            "proof_hash": aiproof.get("proof_hash"),
            "reason": f"Anchoring failed: {exc}",
        }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/health")
def health() -> dict:
    """Liveness probe and a snapshot of the x402 configuration."""
    return {
        "status": "healthy",
        "service": "compli402",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "x402": {
            "facilitator": settings.X402_FACILITATOR_URL or "mock",
            "network": settings.X402_NETWORK,
            "price_usdc": settings.X402_PRICE_USDC,
            "mock_mode": settings.X402_MOCK_MODE,
        },
        "proofs_stored": len(_PROOF_STORE),
    }


@router.post("/verify/intent", response_model=Compli402VerifyResponse)
def verify_intent(intent: Compli402Intent) -> Compli402VerifyResponse:
    """Evaluate an intent against governance policy without executing it."""
    transaction_id, decision = _evaluate_intent(intent)

    if decision.result == DecisionResult.DENIED:
        return Compli402VerifyResponse(
            transaction_id=transaction_id,
            decision=_decision_summary(decision),
            status=Compli402Status.DENIED,
            payment_required=False,
            message="Intent denied by governance policy.",
        )

    if decision.result == DecisionResult.ESCALATED:
        return Compli402VerifyResponse(
            transaction_id=transaction_id,
            decision=_decision_summary(decision),
            status=Compli402Status.ESCALATION_REQUIRED,
            payment_required=False,
            message="Intent requires escalation / human approval.",
        )

    # APPROVED (or any non-deny/non-escalate result) → payment is required.
    return Compli402VerifyResponse(
        transaction_id=transaction_id,
        decision=_decision_summary(decision),
        status=Compli402Status.PAYMENT_REQUIRED,
        payment_required=True,
        message="Intent approved. x402 payment required to execute.",
    )


@router.post("/execute", response_model=Compli402ExecuteResponse)
async def execute(
    intent: Compli402Intent, response: Response
) -> Compli402ExecuteResponse:
    """Run the full Compli402 governance → payment → execute → anchor flow."""
    transaction_id, decision = _evaluate_intent(intent)
    decision_summary = _decision_summary(decision)

    # 3. DENY → stop.
    if decision.result == DecisionResult.DENIED:
        return Compli402ExecuteResponse(
            transaction_id=transaction_id,
            decision=decision_summary,
            status=Compli402Status.DENIED,
            message="Intent denied by governance policy.",
        )

    # 4. ESCALATE → escalation required.
    if decision.result == DecisionResult.ESCALATED:
        return Compli402ExecuteResponse(
            transaction_id=transaction_id,
            decision=decision_summary,
            status=Compli402Status.ESCALATION_REQUIRED,
            message="Intent requires escalation / human approval.",
        )

    # 5. APPROVE → require x402 payment and attempt execution.
    adapter = X402Adapter()
    execution = await adapter.execute(
        transaction_id=transaction_id,
        amount=intent.amount,
        currency=intent.currency,
        metadata={"approved": True, "payment": intent.payment},
    )

    payment_context = {
        "payment_required": execution.get("payment_required"),
        "payment_verified": execution.get("payment_verified"),
        "payment_reference": execution.get("payment_reference"),
        "facilitator": execution.get("facilitator"),
        "network": execution.get("network"),
        "amount": execution.get("amount"),
    }

    # 6. Payment missing → 402-style payment required response.
    if execution.get("status") == "PAYMENT_REQUIRED":
        response.status_code = status.HTTP_402_PAYMENT_REQUIRED
        return Compli402ExecuteResponse(
            transaction_id=transaction_id,
            decision=decision_summary,
            status=Compli402Status.PAYMENT_REQUIRED,
            payment={**payment_context, "accepts": execution.get("accepts")},
            execution=execution,
            message="x402 payment required to execute the approved action.",
        )

    # Payment supplied but not verified → payment failed.
    if not execution.get("payment_verified"):
        response.status_code = status.HTTP_402_PAYMENT_REQUIRED
        return Compli402ExecuteResponse(
            transaction_id=transaction_id,
            decision=decision_summary,
            status=Compli402Status.PAYMENT_FAILED,
            payment=payment_context,
            execution=execution,
            message=execution.get("error", "x402 payment verification failed."),
        )

    # 7. Payment verified → action executed. 8/9. Generate + anchor AIProof.
    aiproof = _build_aiproof(
        transaction_id=transaction_id,
        intent=intent,
        decision=decision,
        execution=execution,
    )
    anchor_receipt = _anchor_proof(aiproof)
    _store_proof(aiproof["proof_hash"], aiproof)

    # 10. Return execution result, AIProof bundle, and anchor receipt.
    return Compli402ExecuteResponse(
        transaction_id=transaction_id,
        decision=decision_summary,
        status=Compli402Status.EXECUTED,
        payment=payment_context,
        execution=execution,
        proof=aiproof,
        anchor=anchor_receipt,
        message="Approved action executed and AIProof anchored.",
    )


@router.get("/proofs/latest")
def latest_proof() -> dict:
    """Return the most recently generated AIProof bundle."""
    if not _PROOF_ORDER:
        raise HTTPException(status_code=404, detail="No proofs available yet.")
    return _PROOF_STORE[_PROOF_ORDER[-1]]


@router.get("/proofs/{proof_hash}")
def get_proof(proof_hash: str) -> dict:
    """Return a single AIProof bundle by its proof hash."""
    proof = _PROOF_STORE.get(proof_hash)
    if proof is None:
        raise HTTPException(status_code=404, detail=f"Proof not found: {proof_hash}")
    return proof
