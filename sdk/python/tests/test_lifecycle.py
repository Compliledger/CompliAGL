import pathlib
import uuid

import pytest

from compliagl import CompliAGL, ConflictError, ExecutionResultStatus, ExternalExecutionResult, ValidationError, sign_execution_result


def make_signed_result(auth_id, amount=750, payload=None):
    now = "2026-08-02T13:00:00Z"
    result = ExternalExecutionResult(
        execution_result_id=str(uuid.uuid4()),
        authorization_id=auth_id,
        external_system_id="outside_commerce_system",
        status=ExecutionResultStatus.SUCCEEDED,
        executed_action="fulfill_generic_order",
        target={"offer_id": "offer_123"},
        amount_minor=amount,
        amount_currency="USD",
        external_reference="order_123",
        payment_or_settlement_reference="settlement_123",
        result_payload_hash="",
        executed_at=now,
        submitted_at=now,
        signer_key_id="",
        signature="",
        provenance={"system": "external-demo", "adapter": "simulated"},
        result_payload=payload or {"order_id": "order_123", "amount_minor": amount, "fulfilled": True},
    )
    return sign_execution_result(result, "test-secret", "test-key")


def prepare_lifecycle(sdk: CompliAGL):
    offer = {"offer_id": "offer_123", "amount_minor": 750, "currency": "USD"}
    actor = sdk.actor_identities.create({"actor_type": "SERVICE", "credential_type": "NONE", "display_name": "Outside App"})
    intent = sdk.intents.create({"actor_identity_id": actor["id"], "intent_type": "PAYMENT", "status": "SUBMITTED", "amount_minor": offer["amount_minor"], "amount_currency": offer["currency"]})
    target = sdk.targets.create({"target_type": "MERCHANT", "name": "Generic external marketplace", "external_id": offer["offer_id"]})
    context = sdk.operational_contexts.create({"environment": "TEST", "intent_id": intent["id"], "target_id": target["id"]})
    evaluation = sdk.evaluations.create({"intent_id": intent["id"], "target_id": target["id"], "operational_context_id": context["id"]})
    resolved = sdk.evaluations.resolve(evaluation["id"], "APPROVED", ["MOCK_APPROVED"], "RESOLVED")
    decision = sdk.decisions.decide("org_test", resolved["id"])
    authorization = sdk.authorizations.issue({"decision_id": decision["id"], "max_amount_minor": 1000, "amount_currency": "USD"})
    verified = sdk.verification.verify_authorization(authorization["id"], {"amount_currency": "USD"})
    assert verified["valid"] is True
    return authorization


def test_full_end_to_end_lifecycle_produces_verifiable_aiproof(sdk):
    authorization = prepare_lifecycle(sdk)
    result = make_signed_result(authorization["id"])
    assert sdk.verification.verify_execution_result_binding(result.to_dict(), "test-secret") is True
    submitted = sdk.execution_results.create(result)
    proof = sdk.aiproofs.generate(submitted["execution_result_id"])
    fetched = sdk.aiproofs.get(proof["id"])
    verification = sdk.verification.verify_proof(fetched["id"])
    assert verification["valid"] is True


def test_altered_result_rejection(sdk):
    authorization = prepare_lifecycle(sdk)
    too_much = make_signed_result(authorization["id"], amount=1500)
    with pytest.raises(ConflictError):
        sdk.execution_results.create(too_much)
    changed_payload = make_signed_result(authorization["id"])
    tampered = changed_payload.to_dict()
    tampered["result_payload"] = {"order_id": "order_123", "amount_minor": 1, "fulfilled": True}
    with pytest.raises(ValidationError):
        sdk.execution_results.create(tampered)


def test_sdk_core_contains_no_policy_decision_logic():
    root = pathlib.Path(__file__).resolve().parents[1] / "compliagl"
    forbidden = ["amount_minor <=", "amount_minor<", "outcome =", "outcome=", "MOCK_APPROVED"]
    for path in root.rglob("*.py"):
        if path.name == "enums.py":
            continue
        text = path.read_text()
        assert not any(token in text for token in forbidden), f"policy-like token in {path}"
