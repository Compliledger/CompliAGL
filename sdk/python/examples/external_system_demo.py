from __future__ import annotations

import os
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from compliagl import CompliAGL, CompliAGLConfig, ExecutionResultStatus, ExternalExecutionResult, sign_execution_result


class SimulatedExternalCommerceSystem:
    """This adapter is outside CompliAGL; it performs the simulated real-world action."""

    def select_offer(self):
        return {"offer_id": "generic-offer-001", "description": "Generic service package", "amount_minor": 750, "currency": "USD"}

    def execute(self, authorization, params):
        return {
            "order_id": "order-" + uuid.uuid4().hex[:8],
            "fulfilled": True,
            "amount_minor": params["amount_minor"],
            "currency": params["currency"],
        }


def main():
    mock = None
    base_url = os.environ.get("COMPLIAGL_BASE_URL")
    if not base_url:
        from tests.mock_server import MockCompliAGLServer

        mock = MockCompliAGLServer().start()
        base_url = mock.base_url
        print(f"Using in-process mock CompliAGL server at {base_url}")
    try:
        org_id = os.environ.get("COMPLIAGL_ORG_ID", "org_demo")
        api_key = os.environ.get("COMPLIAGL_API_KEY")
        sdk = CompliAGL(CompliAGLConfig(base_url=base_url, organization_id=org_id, api_key=api_key, auto_idempotency=True, retry_base_ms=0))
        external = SimulatedExternalCommerceSystem()

        print("1. [EXTERNAL] OUTSIDE CompliAGL: select an offer")
        offer = external.select_offer()
        print("   ", offer)

        print("2. [SDK->CompliAGL] create actor identity, intent, target, and operational context")
        actor = sdk.actor_identities.create({"actor_type": "SERVICE", "credential_type": "NONE", "display_name": "External commerce app"})
        intent = sdk.intents.create({"actor_identity_id": actor["id"], "intent_type": "PAYMENT", "status": "SUBMITTED", "amount_minor": offer["amount_minor"], "amount_currency": offer["currency"]})
        target = sdk.targets.create({"target_type": "MERCHANT", "name": "Generic external marketplace", "external_id": offer["offer_id"]})
        context = sdk.operational_contexts.create({"environment": "TEST", "intent_id": intent["id"], "target_id": target["id"]})

        print("3. [SDK->CompliAGL] request evaluation, resolve it in mock, and read a server decision")
        evaluation = sdk.evaluations.create({"intent_id": intent["id"], "target_id": target["id"], "operational_context_id": context["id"]})
        sdk.evaluations.resolve(evaluation["id"], "APPROVED", ["MOCK_APPROVED"], "RESOLVED")
        decision = sdk.decisions.decide(org_id, evaluation["id"])
        print("   Decision outcome from CompliAGL:", decision["outcome"])

        print("4. [SDK->CompliAGL] issue signed execution authorization")
        authorization = sdk.authorizations.issue({"decision_id": decision["id"], "max_amount_minor": 1000, "amount_currency": "USD"})

        print("5. [SDK] verify authorization structure with CompliAGL")
        print("   ", sdk.verification.verify_authorization(authorization["id"], {"amount_currency": "USD"})["valid"])

        print("6. [EXTERNAL] OUTSIDE CompliAGL: perform the real action")
        outcome = external.execute(authorization, offer)
        print("   ", outcome)

        print("7. [SDK] sign and submit the ExternalExecutionResult")
        now = "2026-08-02T13:00:00Z"
        unsigned = ExternalExecutionResult(
            execution_result_id=str(uuid.uuid4()),
            authorization_id=authorization["id"],
            external_system_id="external-commerce-demo",
            status=ExecutionResultStatus.SUCCEEDED,
            executed_action="fulfill_generic_order",
            target={"offer_id": offer["offer_id"]},
            amount_minor=offer["amount_minor"],
            amount_currency=offer["currency"],
            external_reference=outcome["order_id"],
            payment_or_settlement_reference="settlement-" + outcome["order_id"],
            result_payload_hash="",
            executed_at=now,
            submitted_at=now,
            signer_key_id="",
            signature="",
            provenance={"system": "SimulatedExternalCommerceSystem", "outside_compliagl": True},
            result_payload=outcome,
        )
        result = sign_execution_result(unsigned, "demo-secret", "demo-key")
        submitted = sdk.execution_results.create(result)

        print("8. [CompliAGL] mock validates authorization/result binding on submit")
        print("   accepted result:", submitted["execution_result_id"])

        print("9. [SDK->CompliAGL] generate, retrieve, and verify AIProof")
        proof = sdk.aiproofs.generate(submitted["execution_result_id"])
        fetched = sdk.aiproofs.get(proof["id"])
        verified = sdk.aiproofs.verify(fetched["id"])
        print("   proof:", fetched["id"], "valid:", verified["valid"])
        print("Lifecycle complete. External execution happened OUTSIDE CompliAGL; CompliAGL authorized and proved it.")
    finally:
        if mock:
            mock.stop()


if __name__ == "__main__":
    main()
