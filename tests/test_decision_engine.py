"""Tests for app.mvp2.core.decision_engine.evaluate_transaction."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.mvp2.core.decision_engine import evaluate_transaction
from app.mvp2.core.reason_codes import (
    ASSET_NOT_ALLOWED,
    CHAIN_NOT_ALLOWED,
    ESCALATION_THRESHOLD_EXCEEDED,
    INVALID_AMOUNT,
    MAX_AMOUNT_EXCEEDED,
    VENDOR_NOT_ALLOWED,
    WITHIN_POLICY,
)
from app.mvp2.schemas.decision import DecisionStatus
from app.mvp2.schemas.policy import PolicyDefinition
from app.mvp2.schemas.transaction import TransactionRequest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def policy() -> PolicyDefinition:
    return PolicyDefinition(
        policy_id="pol-001",
        policy_name="Test Policy",
        policy_version="1.0",
        actor_id="actor-001",
        max_amount=10000.0,
        escalation_threshold=5000.0,
        allowed_vendors=["VendorA", "VendorB"],
        allowed_chains=["Ethereum", "Polygon"],
        allowed_assets=["USDC", "USDT"],
    )


def _txn(**overrides) -> TransactionRequest:
    """Build a valid transaction, applying *overrides*."""
    defaults = dict(
        transaction_id="txn-001",
        actor_id="actor-001",
        vendor="VendorA",
        chain="Ethereum",
        asset_symbol="USDC",
        amount=1000.0,
        destination="0xABC",
    )
    defaults.update(overrides)
    return TransactionRequest(**defaults)


# ---------------------------------------------------------------------------
# APPROVE path
# ---------------------------------------------------------------------------

class TestApprove:
    def test_within_policy(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(amount=100.0), policy)
        assert result.decision == DecisionStatus.APPROVE
        assert WITHIN_POLICY in result.reason_codes

    def test_result_contains_policy_metadata(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(), policy)
        assert result.policy_id == "pol-001"
        assert result.policy_version == "1.0"

    def test_timestamp_is_utc_iso(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(), policy)
        # Must parse as valid ISO-8601
        parsed = datetime.fromisoformat(result.timestamp)
        assert parsed.tzinfo is not None  # timezone-aware

    def test_at_escalation_threshold_still_approves(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(amount=5000.0), policy)
        assert result.decision == DecisionStatus.APPROVE
        assert WITHIN_POLICY in result.reason_codes


# ---------------------------------------------------------------------------
# ESCALATE path
# ---------------------------------------------------------------------------

class TestEscalate:
    def test_above_escalation_threshold(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(amount=7500.0), policy)
        assert result.decision == DecisionStatus.ESCALATE
        assert ESCALATION_THRESHOLD_EXCEEDED in result.reason_codes

    def test_just_above_escalation_threshold(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(amount=5000.01), policy)
        assert result.decision == DecisionStatus.ESCALATE

    def test_at_max_amount_escalates(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(amount=10000.0), policy)
        assert result.decision == DecisionStatus.ESCALATE
        assert ESCALATION_THRESHOLD_EXCEEDED in result.reason_codes


# ---------------------------------------------------------------------------
# DENY path
# ---------------------------------------------------------------------------

class TestDeny:
    def test_amount_zero(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(amount=0), policy)
        assert result.decision == DecisionStatus.DENY
        assert INVALID_AMOUNT in result.reason_codes

    def test_negative_amount(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(amount=-50), policy)
        assert result.decision == DecisionStatus.DENY
        assert INVALID_AMOUNT in result.reason_codes

    def test_vendor_not_allowed(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(vendor="BadVendor"), policy)
        assert result.decision == DecisionStatus.DENY
        assert VENDOR_NOT_ALLOWED in result.reason_codes

    def test_chain_not_allowed(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(chain="Solana"), policy)
        assert result.decision == DecisionStatus.DENY
        assert CHAIN_NOT_ALLOWED in result.reason_codes

    def test_asset_not_allowed(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(asset_symbol="DOGE"), policy)
        assert result.decision == DecisionStatus.DENY
        assert ASSET_NOT_ALLOWED in result.reason_codes

    def test_amount_exceeds_max(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(_txn(amount=10001.0), policy)
        assert result.decision == DecisionStatus.DENY
        assert MAX_AMOUNT_EXCEEDED in result.reason_codes

    def test_multiple_deny_reasons(self, policy: PolicyDefinition) -> None:
        result = evaluate_transaction(
            _txn(amount=-1, vendor="X", chain="X", asset_symbol="X"), policy
        )
        assert result.decision == DecisionStatus.DENY
        assert INVALID_AMOUNT in result.reason_codes
        assert VENDOR_NOT_ALLOWED in result.reason_codes
        assert CHAIN_NOT_ALLOWED in result.reason_codes
        assert ASSET_NOT_ALLOWED in result.reason_codes
