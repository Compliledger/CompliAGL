"""Tests for CompliAGL business enums and domain constants."""

import pytest

from app.utils.enums import (
    ActorType,
    ApprovalStatus,
    DecisionResult,
    PolicyStatus,
    ProofStatus,
    RiskLevel,
    TransactionStatus,
)


class TestDecisionResult:
    def test_members(self):
        assert set(DecisionResult) == {
            DecisionResult.APPROVED,
            DecisionResult.DENIED,
            DecisionResult.ESCALATED,
            DecisionResult.PENDING_APPROVAL,
        }

    def test_values(self):
        assert DecisionResult.APPROVED.value == "APPROVED"
        assert DecisionResult.DENIED.value == "DENIED"
        assert DecisionResult.ESCALATED.value == "ESCALATED"
        assert DecisionResult.PENDING_APPROVAL.value == "PENDING_APPROVAL"

    def test_string_behaviour(self):
        """Enum members behave as plain strings (str, Enum)."""
        assert DecisionResult.APPROVED == "APPROVED"
        assert isinstance(DecisionResult.APPROVED, str)

    def test_lookup_from_value(self):
        assert DecisionResult("APPROVED") is DecisionResult.APPROVED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            DecisionResult("INVALID")

    def test_approved_means_proceed(self):
        """Business rule: APPROVED means the transaction can proceed."""
        assert DecisionResult.APPROVED.value == "APPROVED"

    def test_denied_means_blocked(self):
        """Business rule: DENIED means blocked by policy."""
        assert DecisionResult.DENIED.value == "DENIED"

    def test_escalated_means_human_review(self):
        """Business rule: ESCALATED requires human or second-wallet approval."""
        assert DecisionResult.ESCALATED.value == "ESCALATED"

    def test_pending_approval_means_waiting(self):
        """Business rule: PENDING_APPROVAL means waiting after escalation."""
        assert DecisionResult.PENDING_APPROVAL.value == "PENDING_APPROVAL"


class TestTransactionStatus:
    def test_members(self):
        expected = {
            TransactionStatus.SUBMITTED,
            TransactionStatus.EVALUATED,
            TransactionStatus.APPROVED,
            TransactionStatus.DENIED,
            TransactionStatus.ESCALATED,
            TransactionStatus.EXECUTED,
            TransactionStatus.FAILED,
        }
        assert set(TransactionStatus) == expected

    def test_values(self):
        for member in TransactionStatus:
            assert member.value == member.name

    def test_string_behaviour(self):
        assert TransactionStatus.SUBMITTED == "SUBMITTED"


class TestApprovalStatus:
    def test_members(self):
        assert set(ApprovalStatus) == {
            ApprovalStatus.PENDING,
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
        }

    def test_values(self):
        assert ApprovalStatus.PENDING.value == "PENDING"
        assert ApprovalStatus.APPROVED.value == "APPROVED"
        assert ApprovalStatus.REJECTED.value == "REJECTED"


class TestActorType:
    def test_members(self):
        assert set(ActorType) == {
            ActorType.AGENT,
            ActorType.HUMAN,
            ActorType.ORGANIZATION,
        }

    def test_values(self):
        assert ActorType.AGENT.value == "AGENT"
        assert ActorType.HUMAN.value == "HUMAN"
        assert ActorType.ORGANIZATION.value == "ORGANIZATION"


class TestPolicyStatus:
    def test_members(self):
        assert set(PolicyStatus) == {
            PolicyStatus.ACTIVE,
            PolicyStatus.INACTIVE,
        }

    def test_values(self):
        assert PolicyStatus.ACTIVE.value == "ACTIVE"
        assert PolicyStatus.INACTIVE.value == "INACTIVE"


class TestRiskLevel:
    def test_members(self):
        assert set(RiskLevel) == {
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
        }

    def test_values(self):
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.MEDIUM.value == "MEDIUM"
        assert RiskLevel.HIGH.value == "HIGH"


class TestProofStatus:
    def test_members(self):
        assert set(ProofStatus) == {
            ProofStatus.GENERATED,
            ProofStatus.ANCHORED,
            ProofStatus.FAILED,
        }

    def test_values(self):
        assert ProofStatus.GENERATED.value == "GENERATED"
        assert ProofStatus.ANCHORED.value == "ANCHORED"
        assert ProofStatus.FAILED.value == "FAILED"


class TestEnumConsistency:
    """Verify enums are used consistently across models and schemas."""

    def test_decision_result_used_in_schemas(self):
        from app.schemas.schemas import DecisionResponse, ProofRecordResponse

        # The type annotation for result should reference DecisionResult
        assert DecisionResponse.model_fields["result"].annotation is DecisionResult
        assert ProofRecordResponse.model_fields["verdict"].annotation is DecisionResult

    def test_transaction_status_used_in_schemas(self):
        from app.schemas.schemas import TransactionResponse

        assert TransactionResponse.model_fields["status"].annotation is TransactionStatus

    def test_approval_status_used_in_schemas(self):
        from app.schemas.schemas import ApprovalRequestResponse

        assert ApprovalRequestResponse.model_fields["status"].annotation is ApprovalStatus

    def test_policy_status_used_in_schemas(self):
        from app.schemas.schemas import PolicyResponse

        assert PolicyResponse.model_fields["status"].annotation is PolicyStatus

    def test_risk_level_used_in_schemas(self):
        from app.schemas.schemas import PolicyResponse

        assert PolicyResponse.model_fields["risk_level"].annotation is RiskLevel

    def test_proof_status_used_in_schemas(self):
        from app.schemas.schemas import ProofRecordResponse

        assert ProofRecordResponse.model_fields["status"].annotation is ProofStatus

    def test_actor_type_used_in_schemas(self):
        from app.schemas.schemas import AgentResponse

        assert AgentResponse.model_fields["actor_type"].annotation is ActorType

    def test_model_defaults_use_enum_values(self):
        """Model column defaults should match the enum .value strings."""
        from app.models.models import (
            Agent,
            ApprovalRequest,
            Policy,
            ProofRecord,
            Transaction,
        )

        assert Agent.actor_type.default.arg == ActorType.AGENT.value
        assert Policy.status.default.arg == PolicyStatus.ACTIVE.value
        assert Policy.risk_level.default.arg == RiskLevel.LOW.value
        assert Transaction.status.default.arg == TransactionStatus.SUBMITTED.value
        assert ApprovalRequest.status.default.arg == ApprovalStatus.PENDING.value
        assert ProofRecord.status.default.arg == ProofStatus.GENERATED.value
