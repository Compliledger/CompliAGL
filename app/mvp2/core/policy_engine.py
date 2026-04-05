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
