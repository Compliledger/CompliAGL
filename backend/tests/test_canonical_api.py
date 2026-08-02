"""End-to-end API tests for the canonical v1 runtime endpoints."""

from __future__ import annotations

ORG = "org-alpha"
HDR = {"X-Organization-Id": ORG}


def _create(api_client, path, body):
    resp = api_client.post(f"/api/v1/{path}", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_full_runtime_sequence_via_api(api_client):
    # Actor Identity
    actor = _create(
        api_client,
        "actor-identities",
        {
            "organization_id": ORG,
            "actor_type": "AI_AGENT",
            "credential_type": "DID",
            "credential_reference": "did:example:actor#key-1",
            "identity_metadata": {"team": "payments"},
        },
    )

    # Intent (monetary in integer minor units)
    intent = _create(
        api_client,
        "intents",
        {
            "organization_id": ORG,
            "intent_type": "PAYMENT",
            "action": "book_flight",
            "actor_id": actor["id"],
            "amount_minor": 25000,
            "amount_currency": "USD",
            "parameters": {"route": "SFO-JFK"},
        },
    )
    assert intent["amount_minor"] == 25000
    assert intent["integrity_hash"] is not None

    # Target
    target = _create(
        api_client,
        "targets",
        {
            "organization_id": ORG,
            "target_type": "MERCHANT",
            "external_identifier": "airline-01",
        },
    )

    # Operational Context
    context = _create(
        api_client,
        "operational-contexts",
        {
            "organization_id": ORG,
            "environment": "PRODUCTION",
            "allowance_state": {"remaining_minor": 500000, "currency": "USD"},
        },
    )
    assert context["context_hash"] is not None

    # Governance Evaluation ties actor + intent + target + context
    evaluation = _create(
        api_client,
        "governance-evaluations",
        {
            "organization_id": ORG,
            "actor_identity_id": actor["id"],
            "intent_id": intent["id"],
            "target_id": target["id"],
            "operational_context_id": context["id"],
        },
    )
    assert evaluation["status"] == "PENDING"

    # Resolve evaluation
    resolved = api_client.post(
        f"/api/v1/governance-evaluations/{evaluation['id']}/resolve",
        json={"outcome": "APPROVED", "reason_codes": ["OK"]},
        headers=HDR,
    )
    assert resolved.status_code == 200
    assert resolved.json()["outcome"] == "APPROVED"

    # Decision
    decision = _create(
        api_client,
        "decisions",
        {
            "organization_id": ORG,
            "governance_evaluation_id": evaluation["id"],
            "intent_id": intent["id"],
            "outcome": "APPROVED",
            "reason_codes": ["OK"],
        },
    )

    # Execution Authorization
    authorization = _create(
        api_client,
        "execution-authorizations",
        {
            "organization_id": ORG,
            "decision_id": decision["id"],
            "intent_id": intent["id"],
        },
    )
    assert authorization["status"] == "AUTHORIZED"
    assert authorization["authorization_token"]

    # External Execution Result
    result = _create(
        api_client,
        "external-execution-results",
        {
            "organization_id": ORG,
            "execution_authorization_id": authorization["id"],
            "intent_id": intent["id"],
            "adapter": "x402",
            "status": "CONFIRMED",
            "external_reference": "x402-ref-1",
        },
    )
    assert result["status"] == "CONFIRMED"

    # Retrieve the evaluation back
    got = api_client.get(
        f"/api/v1/governance-evaluations/{evaluation['id']}", headers=HDR
    )
    assert got.status_code == 200
    assert got.json()["intent_id"] == intent["id"]


def test_decision_requires_existing_evaluation(api_client):
    resp = api_client.post(
        "/api/v1/decisions",
        json={
            "organization_id": ORG,
            "governance_evaluation_id": "missing",
            "intent_id": "missing",
            "outcome": "APPROVED",
        },
    )
    assert resp.status_code == 404


def test_list_targets_by_type(api_client):
    for target_type in ("MERCHANT", "SMART_CONTRACT", "API"):
        _create(
            api_client,
            "targets",
            {"organization_id": ORG, "target_type": target_type},
        )
    resp = api_client.get("/api/v1/targets", headers=HDR)
    assert resp.status_code == 200
    types = {t["target_type"] for t in resp.json()}
    assert {"MERCHANT", "SMART_CONTRACT", "API"} <= types


def test_invalid_target_type_rejected(api_client):
    resp = api_client.post(
        "/api/v1/targets",
        json={"organization_id": ORG, "target_type": "NOT_A_TYPE"},
    )
    assert resp.status_code == 422
