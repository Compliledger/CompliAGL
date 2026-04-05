"""Reusable helper functions for evaluating transactions against policies."""

from __future__ import annotations

from app.mvp2.core.reason_codes import (
    ASSET_NOT_ALLOWED,
    CHAIN_NOT_ALLOWED,
    INVALID_AMOUNT,
    MAX_AMOUNT_EXCEEDED,
    VENDOR_NOT_ALLOWED,
)
from app.mvp2.schemas.policy import PolicyDefinition
from app.mvp2.schemas.transaction import TransactionRequest

# ---------------------------------------------------------------------------
# In-memory policy registry (MVP 2)
# ---------------------------------------------------------------------------

# Keyed by actor_id – one active policy per actor for MVP 2.
_POLICY_STORE: dict[str, PolicyDefinition] = {}


def seed_demo_policies() -> None:
    """Populate the in-memory registry with demo policies.

    Safe to call multiple times – existing entries are overwritten with the
    canonical demo data.
    """
    demo_policy = PolicyDefinition(
        policy_id="policy-1",
        policy_name="Travel Policy",
        policy_version="v2.0",
        actor_id="actor-1",
        max_amount=500,
        escalation_threshold=250,
        allowed_vendors=["airline_api", "hotel_api", "restaurant_api"],
        allowed_chains=["solana", "x402"],
        allowed_assets=["usdc", "rlusd"],
    )
    _POLICY_STORE[demo_policy.actor_id] = demo_policy


def get_policy_for_actor(actor_id: str) -> PolicyDefinition | None:
    """Return the policy bound to *actor_id*, or ``None`` if not found."""
    return _POLICY_STORE.get(actor_id)


def list_policies() -> list[PolicyDefinition]:
    """Return every policy currently held in the registry."""
    return list(_POLICY_STORE.values())


def vendor_allowed(transaction: TransactionRequest, policy: PolicyDefinition) -> bool:
    """Return *True* if the transaction vendor is in the policy's allowed list."""
    return transaction.vendor in policy.allowed_vendors


def chain_allowed(transaction: TransactionRequest, policy: PolicyDefinition) -> bool:
    """Return *True* if the transaction chain is in the policy's allowed list."""
    return transaction.chain in policy.allowed_chains


def asset_allowed(transaction: TransactionRequest, policy: PolicyDefinition) -> bool:
    """Return *True* if the transaction asset is in the policy's allowed list."""
    return transaction.asset_symbol in policy.allowed_assets


def amount_valid(
    transaction: TransactionRequest, policy: PolicyDefinition
) -> tuple[bool, list[str]]:
    """Validate the transaction amount against the policy.

    Returns a tuple of ``(is_valid, reason_codes)`` where *reason_codes* is an
    empty list when the amount passes all checks.
    """
    reasons: list[str] = []

    if transaction.amount <= 0:
        reasons.append(INVALID_AMOUNT)

    if not vendor_allowed(transaction, policy):
        reasons.append(VENDOR_NOT_ALLOWED)

    if not chain_allowed(transaction, policy):
        reasons.append(CHAIN_NOT_ALLOWED)

    if not asset_allowed(transaction, policy):
        reasons.append(ASSET_NOT_ALLOWED)

    if transaction.amount > policy.max_amount:
        reasons.append(MAX_AMOUNT_EXCEEDED)

    return (len(reasons) == 0, reasons)
