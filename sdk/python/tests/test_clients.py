import pytest

from compliagl import ConflictError, NotFoundError, RateLimitError, ValidationError
from compliagl.config import CompliAGLConfig
from compliagl.client import CompliAGL
from compliagl.http import HttpClient


def test_all_client_crud_and_endpoint_helpers(sdk):
    actor = sdk.actor_identities.create({"actor_type": "SERVICE", "credential_type": "NONE", "display_name": "External worker"})
    assert sdk.actor_identities.get(actor["id"])["id"] == actor["id"]
    assert sdk.actor_identities.update(actor["id"], {"display_name": "Updated"})["display_name"] == "Updated"
    assert sdk.actor_identities.list()["total"] == 1

    intent = sdk.intents.create({"actor_identity_id": actor["id"], "intent_type": "PAYMENT", "status": "PENDING"})
    assert sdk.intents.transition(intent["id"], "SUBMITTED")["status"] == "SUBMITTED"
    target = sdk.targets.create({"target_type": "MERCHANT", "name": "Outside merchant"})
    context = sdk.operational_contexts.create({"environment": "TEST", "intent_id": intent["id"], "target_id": target["id"]})
    evaluation = sdk.evaluations.create({"intent_id": intent["id"], "target_id": target["id"], "operational_context_id": context["id"]})
    assert sdk.evaluations.resolve(evaluation["id"], "APPROVED", ["OK"], "RESOLVED")["outcome"] == "APPROVED"
    assert sdk.evaluations.list()["total"] == 1

    evidence = sdk.evidence.create({"requirement": "receipt", "items": [{"type": "json"}]})
    assert sdk.evidence.get(evidence["job_id"])["status"] == "COMPLETED"
    assert "package_hash" in sdk.evidence.package(evidence["job_id"])
    assert sdk.evidence.sources()["items"]

    decision = sdk.decisions.create({"policy_resolution_id": evaluation["id"], "outcome": "APPROVED"})
    decided = sdk.decisions.decide("org_test", evaluation["id"])
    assert sdk.decisions.get(decision["id"])["id"] == decision["id"]
    assert sdk.decisions.explain(decided["id"])["decision_id"] == decided["id"]

    auth = sdk.authorizations.create({"decision_id": decided["id"], "status": "ISSUED", "max_amount_minor": 1000, "amount_currency": "USD"})
    assert sdk.authorizations.verify(auth["id"], {"amount_currency": "USD"}, activate=True)["valid"] is True
    issued = sdk.authorizations.issue({"decision_id": decided["id"], "max_amount_minor": 1000, "amount_currency": "USD"})
    assert sdk.authorizations.transition(issued["id"], "ACTIVE")["status"] == "ACTIVE"
    assert sdk.authorizations.revoke(issued["id"], "test")["status"] == "REVOKED"


def test_error_mapping(sdk, mock_server):
    with pytest.raises(NotFoundError):
        sdk.actor_identities.get("missing")
    auth = sdk.authorizations.create({"status": "ISSUED", "amount_currency": "USD"})
    with pytest.raises(ConflictError):
        sdk.authorizations.verify(auth["id"], {"amount_currency": "EUR"})
    with pytest.raises(ValidationError):
        sdk.execution_results.create({"execution_result_id": "r"})
    mock_server.state.failures[("GET", "actor-identities")] = 5
    client = CompliAGL(CompliAGLConfig(base_url=mock_server.base_url, organization_id="org", max_retries=0))
    with pytest.raises(Exception) as exc:
        client.actor_identities.list()
    assert getattr(exc.value, "status", None) == 503


def test_retries_and_idempotency(sdk, mock_server):
    mock_server.state.failures[("POST", "actor-identities")] = 1
    first = sdk.actor_identities.create({"display_name": "retry"}, idempotency_key="same-key")
    second = sdk.actor_identities.create({"display_name": "different"}, idempotency_key="same-key")
    assert first == second
    assert mock_server.state.last_headers["Idempotency-Key"] == "same-key"


def test_auto_idempotency_header(mock_server):
    client = CompliAGL(CompliAGLConfig(base_url=mock_server.base_url, organization_id="org", auto_idempotency=True))
    client.actor_identities.create({"display_name": "auto"})
    assert "Idempotency-Key" in mock_server.state.last_headers


def test_auth_and_org_headers(mock_server):
    client = CompliAGL(CompliAGLConfig(base_url=mock_server.base_url, organization_id="org_1", api_key="secret"))
    client.actor_identities.list()
    assert mock_server.state.last_headers["X-Organization-Id"] == "org_1"
    assert mock_server.state.last_headers["Authorization"] == "Bearer " + "secret"
