"""API tests for the Demo #3 orchestration surface: ``GET /demo-runs/{id}``,
``GET /demo-runs``, and ``POST /demo-reset``.

These routes add no governance logic of their own -- see
``app/services/canonical/demo_run_service.py`` and
``demo_reset_service.py``. Exercised here through the real HTTP layer
(``api_client``), independent of the service-level, full-pipeline coverage
in ``test_demo_run_orchestration.py``.
"""

from __future__ import annotations

ORG = "org-demo-runs"
HDR = {"X-Organization-Id": ORG}


def _create(api_client, path, body):
    resp = api_client.post(f"/api/v1/{path}", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_intent(api_client, *, correlation_id, case_id="CASE-001"):
    actor = _create(
        api_client,
        "actor-identities",
        {
            "organization_id": ORG,
            "actor_type": "AI_AGENT",
            "credential_type": "DID",
            "credential_reference": f"did:example:actor#{correlation_id}",
        },
    )
    return _create(
        api_client,
        "intents",
        {
            "organization_id": ORG,
            "intent_type": "TRANSFER",
            "action": "astra_transfer",
            "actor_id": actor["id"],
            "amount_minor": 1000,
            "amount_currency": "USD",
            "correlation_id": correlation_id,
            "parameters": {"compliidentity_resource_instance": case_id},
        },
    )


def test_get_demo_run_404_when_unknown(api_client):
    resp = api_client.get("/api/v1/demo-runs/no-such-correlation-id", headers=HDR)
    assert resp.status_code == 404


def test_get_demo_run_returns_started_stage(api_client):
    intent = _make_intent(api_client, correlation_id="corr-api-1")

    resp = api_client.get("/api/v1/demo-runs/corr-api-1", headers=HDR)
    assert resp.status_code == 200
    body = resp.json()
    assert body["correlation_id"] == "corr-api-1"
    assert body["action_id"] == intent["id"]
    assert body["case_id"] == "CASE-001"
    assert body["stage"] == "STARTED"
    assert body["decision"] is None


def test_list_demo_runs_filters_by_case_id(api_client):
    _make_intent(api_client, correlation_id="corr-api-2", case_id="CASE-A")
    _make_intent(api_client, correlation_id="corr-api-3", case_id="CASE-A")
    _make_intent(api_client, correlation_id="corr-api-4", case_id="CASE-B")

    resp = api_client.get(
        "/api/v1/demo-runs", params={"case_id": "CASE-A"}, headers=HDR
    )
    assert resp.status_code == 200
    runs = resp.json()
    assert {r["correlation_id"] for r in runs} == {"corr-api-2", "corr-api-3"}


def test_demo_reset_clears_run_state_for_this_org_only(api_client):
    _make_intent(api_client, correlation_id="corr-api-reset")

    # A different organization's run data must survive ORG's reset.
    other_org_hdr = {"X-Organization-Id": "org-demo-runs-other"}
    other_actor = _create(
        api_client,
        "actor-identities",
        {
            "organization_id": "org-demo-runs-other",
            "actor_type": "AI_AGENT",
            "credential_type": "DID",
            "credential_reference": "did:example:actor#other-org",
        },
    )
    _create(
        api_client,
        "intents",
        {
            "organization_id": "org-demo-runs-other",
            "intent_type": "TRANSFER",
            "action": "astra_transfer",
            "actor_id": other_actor["id"],
            "correlation_id": "corr-api-other-org",
        },
    )

    resp = api_client.post("/api/v1/demo-reset", headers=HDR)
    assert resp.status_code == 200
    body = resp.json()
    assert body["organization_id"] == ORG
    assert body["deleted"]["intents"] >= 1

    assert api_client.get("/api/v1/demo-runs/corr-api-reset", headers=HDR).status_code == 404
    # A different organization's run data is untouched by ORG's reset.
    other_resp = api_client.get(
        "/api/v1/demo-runs/corr-api-other-org", headers=other_org_hdr
    )
    assert other_resp.status_code == 200
