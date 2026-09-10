"""API-level tests for the Policy Resolution and Applicability Evaluation
endpoints exposed under ``/api/v1``.

These verify the HTTP surface used to *run* and *retrieve* the deterministic
resolution and applicability results end to end.
"""

from __future__ import annotations

ORG = "org-travel"
AUTHOR_HDR = {"X-Organization-Id": ORG, "X-Governance-Role": "COMPLILEDGER_SERVICE"}
READ_HDR = {"X-Organization-Id": ORG}


def _requirements() -> list[dict]:
    return [
        {
            "requirement_id": "REQ-DOMESTIC",
            "source_reference": "TRAVEL §1",
            "normalized_text": "Domestic travel is permitted.",
            "requirement_type": "travel_booking",
            "classification": "PERMISSION",
            "mapped_control_ids": ["CTL-1"],
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.parameters.is_international",
                "value": False,
            },
        },
        {
            "requirement_id": "REQ-JURISDICTION",
            "source_reference": "TRAVEL §2",
            "normalized_text": "Travel restricted to approved jurisdictions.",
            "requirement_type": "location_restriction",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-1"],
            "applicability_criteria": {
                "op": "equals",
                "field": "context.jurisdiction",
                "value": "US",
            },
        },
    ]


def _package_payload() -> dict:
    return {
        "organization_id": ORG,
        "package_name": "travel-policy",
        "package_version": "1.0.0",
        "requirements": _requirements(),
        "control_definitions": [
            {
                "control_id": "CTL-1",
                "requirement_ids": ["REQ-DOMESTIC", "REQ-JURISDICTION"],
                "control_objective": "Bind requirements.",
                "evaluation_expression": "True",
            }
        ],
        "decision_conditions": [
            {
                "condition_id": "DC-1",
                "expression": "True",
                "resulting_decision": "APPROVED",
                "priority": 100,
                "reason_code": "OK",
                "terminal": True,
            }
        ],
        "metadata": {},
    }


def _publish_package(client) -> str:
    resp = client.post("/api/v1/governance-packages", json=_package_payload(), headers=AUTHOR_HDR)
    assert resp.status_code == 201, resp.text
    pkg_id = resp.json()["id"]
    assert client.post(f"/api/v1/governance-packages/{pkg_id}/validate", headers=AUTHOR_HDR).status_code == 200
    assert client.post(
        f"/api/v1/governance-packages/{pkg_id}/approve",
        json={"approver_principal_id": "tester", "rationale": "test approval"},
        headers=AUTHOR_HDR,
    ).status_code == 200
    assert client.post(
        f"/api/v1/governance-packages/{pkg_id}/publish", json={}, headers=AUTHOR_HDR
    ).status_code == 200
    return pkg_id


def _create_inputs(client):
    actor = client.post(
        "/api/v1/actor-identities",
        json={"organization_id": ORG, "actor_type": "HUMAN"},
        headers=AUTHOR_HDR,
    ).json()
    intent = client.post(
        "/api/v1/intents",
        json={
            "organization_id": ORG,
            "intent_type": "WORKFLOW_ACTION",
            "action": "book_travel",
            "actor_id": actor["id"],
            "parameters": {"is_international": False},
        },
        headers=AUTHOR_HDR,
    ).json()
    context = client.post(
        "/api/v1/operational-contexts",
        json={"organization_id": ORG, "jurisdiction": "US", "environment": "PRODUCTION"},
        headers=AUTHOR_HDR,
    ).json()
    return actor, intent, context


def test_policy_resolution_and_applicability_api(api_client):
    _publish_package(api_client)
    actor, intent, context = _create_inputs(api_client)

    # Run policy resolution.
    resp = api_client.post(
        "/api/v1/policy-resolutions",
        json={
            "organization_id": ORG,
            "actor_identity_id": actor["id"],
            "intent_id": intent["id"],
            "operational_context_id": context["id"],
        },
    )
    assert resp.status_code == 201, resp.text
    resolution = resp.json()
    assert resolution["status"] == "RESOLVED"
    assert resolution["engine_version"]
    assert resolution["input_hash"] and resolution["result_hash"]
    assert isinstance(resolution["selected_packages"], list)

    resolution_id = resolution["id"]

    # Retrieve the resolution.
    got = api_client.get(
        f"/api/v1/policy-resolutions/{resolution_id}", headers=READ_HDR
    )
    assert got.status_code == 200
    assert got.json()["id"] == resolution_id

    # Run applicability evaluation.
    resp = api_client.post(
        "/api/v1/applicability-evaluations",
        json={"organization_id": ORG, "policy_resolution_id": resolution_id},
    )
    assert resp.status_code == 201, resp.text
    records = resp.json()
    by_req = {r["requirement_id"]: r for r in records}
    assert by_req["REQ-DOMESTIC"]["result"] == "APPLICABLE"
    assert by_req["REQ-JURISDICTION"]["result"] == "APPLICABLE"
    # Structured expression round-trips as an object.
    assert isinstance(by_req["REQ-DOMESTIC"]["evaluated_expression"], dict)

    # Retrieve applicability results filtered by resolution.
    listed = api_client.get(
        "/api/v1/applicability-evaluations",
        params={"policy_resolution_id": resolution_id},
        headers=READ_HDR,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    # Retrieve a single applicability record.
    single = api_client.get(
        f"/api/v1/applicability-evaluations/{records[0]['id']}", headers=READ_HDR
    )
    assert single.status_code == 200
    assert single.json()["id"] == records[0]["id"]


def test_policy_resolution_missing_input_returns_404(api_client):
    resp = api_client.post(
        "/api/v1/policy-resolutions",
        json={
            "organization_id": ORG,
            "actor_identity_id": "does-not-exist",
            "intent_id": "nope",
        },
    )
    assert resp.status_code == 404


def test_missing_context_indeterminate_via_api(api_client):
    _publish_package(api_client)
    actor, intent, _ = _create_inputs(api_client)

    resp = api_client.post(
        "/api/v1/policy-resolutions",
        json={
            "organization_id": ORG,
            "actor_identity_id": actor["id"],
            "intent_id": intent["id"],
        },
    )
    resolution_id = resp.json()["id"]
    records = api_client.post(
        "/api/v1/applicability-evaluations",
        json={"organization_id": ORG, "policy_resolution_id": resolution_id},
    ).json()
    by_req = {r["requirement_id"]: r for r in records}
    assert by_req["REQ-JURISDICTION"]["result"] == "INDETERMINATE"
    assert by_req["REQ-DOMESTIC"]["result"] == "APPLICABLE"
