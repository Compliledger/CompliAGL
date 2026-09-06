"""API-level tests for the Control Determination and Evidence Requirement
Resolution endpoints exposed under ``/api/v1``.

These verify the HTTP surface used to retrieve the applicable controls and the
resolved evidence requirements for an evaluation (a policy resolution run).
"""

from __future__ import annotations

ORG = "org-travel"
AUTHOR_HDR = {"X-Organization-Id": ORG, "X-Governance-Role": "COMPLILEDGER_SERVICE"}
READ_HDR = {"X-Organization-Id": ORG}


def _package_payload() -> dict:
    return {
        "organization_id": ORG,
        "package_name": "travel-policy",
        "package_version": "1.0.0",
        "requirements": [
            {
                "requirement_id": "REQ-AIRLINE",
                "source_reference": "TRAVEL §1",
                "normalized_text": "Approved airline only.",
                "requirement_type": "vendor_restriction",
                "classification": "OBLIGATION",
                "mapped_control_ids": ["CTL-AIRLINE"],
                "applicability_criteria": {
                    "op": "equals",
                    "field": "target.classification",
                    "value": "AIRLINE",
                },
            },
            {
                "requirement_id": "REQ-SPEND",
                "source_reference": "TRAVEL §2",
                "normalized_text": "Spend limit.",
                "requirement_type": "spend_limit",
                "classification": "OBLIGATION",
                "mapped_control_ids": ["CTL-SPEND"],
                "applicability_criteria": {
                    "op": "equals",
                    "field": "intent.action",
                    "value": "book_travel",
                },
            },
        ],
        "control_definitions": [
            {
                "control_id": "CTL-AIRLINE",
                "requirement_ids": ["REQ-AIRLINE"],
                "control_objective": "Approved airline.",
                "evaluation_expression": "True",
                "evidence_requirement_ids": ["EV-IDENTITY"],
            },
            {
                "control_id": "CTL-SPEND",
                "requirement_ids": ["REQ-SPEND"],
                "control_objective": "Spend limit.",
                "evaluation_expression": "True",
                "evidence_requirement_ids": ["EV-IDENTITY"],
            },
        ],
        "evidence_requirements": [
            {
                "evidence_requirement_id": "EV-IDENTITY",
                "control_ids": ["CTL-AIRLINE", "CTL-SPEND"],
                "evidence_type": "verified_identity",
                "authoritative_source_type": "identity_provider",
                "subject_binding": "actor",
                "minimum_cardinality": 1,
                "mandatory": True,
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
    resp = client.post(
        "/api/v1/governance-packages", json=_package_payload(), headers=AUTHOR_HDR
    )
    assert resp.status_code == 201, resp.text
    pkg_id = resp.json()["id"]
    assert client.post(
        f"/api/v1/governance-packages/{pkg_id}/validate", headers=AUTHOR_HDR
    ).status_code == 200
    assert client.post(
        f"/api/v1/governance-packages/{pkg_id}/approve",
        json={"approver_principal_id": "tester", "rationale": "test approval"},
        headers=AUTHOR_HDR,
    ).status_code == 200
    assert client.post(
        f"/api/v1/governance-packages/{pkg_id}/publish", json={}, headers=AUTHOR_HDR
    ).status_code == 200
    return pkg_id


def _prepare_resolution(client) -> str:
    _publish_package(client)
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
            "amount_minor": 50000,
            "amount_currency": "USD",
            "parameters": {"is_international": False},
        },
        headers=AUTHOR_HDR,
    ).json()
    target = client.post(
        "/api/v1/targets",
        json={
            "organization_id": ORG,
            "target_type": "MERCHANT",
            "external_identifier": "airline-01",
            "classification": "AIRLINE",
        },
        headers=AUTHOR_HDR,
    ).json()
    context = client.post(
        "/api/v1/operational-contexts",
        json={"organization_id": ORG, "jurisdiction": "US", "environment": "PRODUCTION"},
        headers=AUTHOR_HDR,
    ).json()
    resolution = client.post(
        "/api/v1/policy-resolutions",
        json={
            "organization_id": ORG,
            "actor_identity_id": actor["id"],
            "intent_id": intent["id"],
            "target_id": target["id"],
            "operational_context_id": context["id"],
        },
    ).json()
    resolution_id = resolution["id"]
    # Run applicability so the controls have a basis.
    assert client.post(
        "/api/v1/applicability-evaluations",
        json={"organization_id": ORG, "policy_resolution_id": resolution_id},
    ).status_code == 201
    return resolution_id


def test_get_evaluation_controls(api_client):
    resolution_id = _prepare_resolution(api_client)

    resp = api_client.get(
        f"/api/v1/evaluations/{resolution_id}/controls", headers=READ_HDR
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["policy_resolution_id"] == resolution_id
    assert body["engine_version"]
    assert body["input_hash"] and body["result_hash"]
    control_ids = {c["control_id"] for c in body["controls"]}
    assert {"CTL-AIRLINE", "CTL-SPEND"} <= control_ids
    for ctrl in body["controls"]:
        assert ctrl["status"] == "APPLICABLE"
        assert ctrl["governance_packages"][0]["package_version"] == "1.0.0"


def test_get_evaluation_evidence_requirements(api_client):
    resolution_id = _prepare_resolution(api_client)

    resp = api_client.get(
        f"/api/v1/evaluations/{resolution_id}/evidence-requirements",
        headers=READ_HDR,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["policy_resolution_id"] == resolution_id
    assert body["applicable_control_set_id"]
    by_id = {e["evidence_requirement_id"]: e for e in body["evidence_requirements"]}
    identity = by_id["EV-IDENTITY"]
    assert identity["state"] == "REQUIRED"
    # Shared evidence deduplicated to a single entry mapping to both controls.
    assert identity["control_ids"] == ["CTL-AIRLINE", "CTL-SPEND"]


def test_get_controls_for_unknown_evaluation_returns_404(api_client):
    resp = api_client.get(
        "/api/v1/evaluations/does-not-exist/controls", headers=READ_HDR
    )
    assert resp.status_code == 404


def test_get_evidence_for_unknown_evaluation_returns_404(api_client):
    resp = api_client.get(
        "/api/v1/evaluations/does-not-exist/evidence-requirements",
        headers=READ_HDR,
    )
    assert resp.status_code == 404
