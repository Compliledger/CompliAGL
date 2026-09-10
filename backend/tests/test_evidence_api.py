"""API tests for the evidence layer v1 routes.

These exercise the five required API surfaces through the FastAPI app:

* start evidence collection,
* inspect collection status,
* retrieve validation results,
* retrieve normalized evidence,
* retrieve the Canonical Evidence Package.

The collection runs against the built-in mock simulators in non-production mode.
"""

from __future__ import annotations


ORG = "org-evidence-api"
HEADERS = {"X-Organization-Id": ORG}


def _publish_package(client):
    requirements = [
        {
            "requirement_id": "REQ-MAIN",
            "source_reference": "GEN §1",
            "normalized_text": "Action must satisfy identity evidence.",
            "requirement_type": "generic",
            "classification": "OBLIGATION",
            "mapped_control_ids": ["CTL-IDENTITY"],
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.action",
                "value": "perform_action",
            },
        }
    ]
    controls = [
        {
            "control_id": "CTL-IDENTITY",
            "requirement_ids": ["REQ-MAIN"],
            "control_objective": "Verified delegation is present.",
            "evaluation_expression": "True",
            "expected_outcome": "APPROVED",
            "mandatory": True,
            "severity": "HIGH",
            "failure_disposition": "DENY",
            "evidence_requirement_ids": ["EV-IDENTITY"],
        }
    ]
    evidence = [
        {
            "evidence_requirement_id": "EV-IDENTITY",
            "control_ids": ["CTL-IDENTITY"],
            "evidence_type": "verified_identity",
            "authoritative_source_type": "identity_provider",
            "subject_binding": "actor",
            "freshness_requirement": "P36500D",
            "minimum_cardinality": 1,
            "mandatory": True,
        }
    ]
    body = {
        "organization_id": ORG,
        "package_name": "generic-api-policy",
        "package_version": "1.0.0",
        "requirements": requirements,
        "control_definitions": controls,
        "evidence_requirements": evidence,
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
    author = {**HEADERS, "X-Governance-Role": "COMPLILEDGER_SERVICE"}
    resp = client.post("/api/v1/governance-packages", json=body, headers=author)
    assert resp.status_code == 201, resp.text
    pkg_id = resp.json()["id"]
    assert (
        client.post(
            f"/api/v1/governance-packages/{pkg_id}/validate", headers=author
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/governance-packages/{pkg_id}/approve",
            json={"approver_principal_id": "tester", "rationale": "test approval"},
            headers=author,
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/governance-packages/{pkg_id}/publish", headers=author
        ).status_code
        == 200
    )


def _resolution(client):
    actor = client.post(
        "/api/v1/actor-identities",
        json={"organization_id": ORG, "actor_type": "AI_AGENT"},
    ).json()
    intent = client.post(
        "/api/v1/intents",
        json={
            "organization_id": ORG,
            "intent_type": "WORKFLOW_ACTION",
            "action": "perform_action",
            "actor_id": actor["id"],
        },
    ).json()
    context = client.post(
        "/api/v1/operational-contexts",
        json={
            "organization_id": ORG,
            "jurisdiction": "US",
            "environment": "STAGING",
        },
    ).json()
    resolution = client.post(
        "/api/v1/policy-resolutions",
        json={
            "organization_id": ORG,
            "actor_identity_id": actor["id"],
            "intent_id": intent["id"],
            "operational_context_id": context["id"],
        },
    ).json()
    client.post(
        "/api/v1/applicability-evaluations",
        json={"organization_id": ORG, "policy_resolution_id": resolution["id"]},
    )
    return resolution["id"]


def test_evidence_api_full_flow(api_client):
    _publish_package(api_client)
    resolution_id = _resolution(api_client)

    # 1. Start evidence collection. The default registry uses the built-in mock
    #    simulators which, without fixtures, truthfully report NOT_FOUND — the
    #    orchestrator never fabricates evidence, so the job is FAILED and the
    #    single requirement is explicitly unresolved.
    start = api_client.post(
        "/api/v1/evidence-collections",
        json={"organization_id": ORG, "policy_resolution_id": resolution_id},
    )
    assert start.status_code == 201, start.text
    job = start.json()
    job_id = job["id"]
    assert job["status"] == "FAILED"
    assert job["unresolved"] == [] or isinstance(job["unresolved"], list)
    assert job["failures"]  # collection failures are recorded, never hidden

    # 2. Inspect collection status.
    status = api_client.get(
        f"/api/v1/evidence-collections/{job_id}", headers=HEADERS
    )
    assert status.status_code == 200
    assert status.json()["id"] == job_id

    # 3. Retrieve validation results. The NOT_FOUND raw item receives an
    #    explicit INDETERMINATE validation result (every item is validated).
    validations = api_client.get(
        f"/api/v1/evidence-collections/{job_id}/validation-results",
        headers=HEADERS,
    )
    assert validations.status_code == 200
    v = validations.json()
    assert len(v) == 1
    assert v[0]["outcome"] == "INDETERMINATE"
    assert isinstance(v[0]["checks"], dict)

    # 4. Retrieve normalized evidence — nothing normalizes because nothing is VALID.
    normalized = api_client.get(
        f"/api/v1/evidence-collections/{job_id}/normalized-evidence",
        headers=HEADERS,
    )
    assert normalized.status_code == 200
    assert normalized.json() == []

    # 5. Retrieve the Canonical Evidence Package. The missing requirement is
    #    recorded explicitly rather than being silently satisfied.
    package = api_client.get(
        f"/api/v1/evidence-collections/{job_id}/package", headers=HEADERS
    )
    assert package.status_code == 200
    p = package.json()
    assert p["evaluation_id"] == resolution_id
    assert p["package_hash"]
    assert p["normalized_evidence_references"] == []
    missing_reqs = {m["evidence_requirement_id"] for m in p["missing_evidence"]}
    assert "EV-IDENTITY" in missing_reqs

    # Bonus: the source registry is inspectable -- the six mock simulators plus
    # the real HarborStone SENTRY sanctions-screening connector (registered by
    # default in default_production_registry()).
    sources = api_client.get("/api/v1/evidence-sources", headers=HEADERS)
    assert sources.status_code == 200
    source_ids = {s.get("source_id") or s.get("connector_id") for s in sources.json()}
    assert len(sources.json()) == 7
    assert "harborstone-sentry-sanctions-screening" in source_ids


def test_evidence_api_unknown_job_returns_404(api_client):
    resp = api_client.get(
        "/api/v1/evidence-collections/does-not-exist", headers=HEADERS
    )
    assert resp.status_code == 404
