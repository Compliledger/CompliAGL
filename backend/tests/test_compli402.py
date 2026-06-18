"""Tests for the Compli402 public API endpoints."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mvp2.core.policy_engine import seed_demo_policies
from app.mvp2.identity.actors import seed_demo_actors

# Demo actor seeded by seed_demo_actors (TravelAgent-01).
DEMO_ACTOR_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True)
def seed():
    """Seed the in-memory demo actors and policies for each test."""
    seed_demo_actors()
    seed_demo_policies()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def _intent(amount: float, currency: str = "USDC", payment=None):
    body = {"actor_id": DEMO_ACTOR_ID, "action": "book_flight", "amount": amount,
            "currency": currency}
    if payment is not None:
        body["payment"] = payment
    return body


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/api/compli402/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "compli402"
    assert "x402" in data
    assert "network" in data["x402"]


# ---------------------------------------------------------------------------
# verify/intent
# ---------------------------------------------------------------------------


def test_verify_intent_approved_requires_payment(client):
    resp = client.post("/api/compli402/verify/intent", json=_intent(100.0))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PAYMENT_REQUIRED"
    assert data["payment_required"] is True
    assert data["decision"]["result"] == "APPROVED"


def test_verify_intent_denied(client):
    # Amount above max_amount (500) → DENIED.
    resp = client.post("/api/compli402/verify/intent", json=_intent(600.0))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "DENIED"
    assert data["payment_required"] is False


def test_verify_intent_escalated(client):
    # Amount above escalation_threshold (250) but below max (500) → ESCALATED.
    resp = client.post("/api/compli402/verify/intent", json=_intent(300.0))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ESCALATION_REQUIRED"


def test_verify_intent_unknown_actor(client):
    body = _intent(100.0)
    body["actor_id"] = "11111111-1111-1111-1111-111111111111"
    resp = client.post("/api/compli402/verify/intent", json=body)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------


def test_execute_denied(client):
    resp = client.post("/api/compli402/execute", json=_intent(600.0))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "DENIED"
    assert data["proof"] is None


def test_execute_escalated(client):
    resp = client.post("/api/compli402/execute", json=_intent(300.0))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ESCALATION_REQUIRED"


def test_execute_payment_required_returns_402(client):
    resp = client.post("/api/compli402/execute", json=_intent(100.0))
    assert resp.status_code == 402
    data = resp.json()
    assert data["status"] == "PAYMENT_REQUIRED"
    assert data["payment"]["payment_required"] is True
    assert data["payment"]["payment_verified"] is False


def test_execute_with_payment_executes_and_anchors(client):
    resp = client.post(
        "/api/compli402/execute",
        json=_intent(100.0, payment={"reference": "pay-abc-123"}),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "EXECUTED"
    assert data["payment"]["payment_verified"] is True
    assert data["proof"] is not None
    proof = data["proof"]
    assert proof["proof_hash"]
    assert data["execution"]["execution_reference"]
    # Anchor receipt is always present (degrades gracefully when adapter absent).
    assert data["anchor"] is not None

    # AIProof bundle exposes the full x402-challenge schema.
    expected_fields = {
        "proof_id", "proof_type", "actor_id", "actor_identity", "intent_id",
        "intent", "policy_id", "policy_version", "decision", "decision_reason",
        "execution_adapter", "execution_status", "payment_protocol",
        "payment_reference", "settlement_chain", "anchor_chain", "anchor_tx_id",
        "proof_hash", "created_at", "verification_url",
    }
    assert expected_fields.issubset(set(proof.keys()))
    assert proof["decision"] == "APPROVED"
    assert proof["execution_adapter"] == "x402"
    assert proof["payment_protocol"] == "x402"
    assert proof["execution_status"] == "CONFIRMED"
    assert proof["payment_reference"]
    assert proof["actor_id"] == DEMO_ACTOR_ID
    # Post-hash field populated after anchoring.
    assert proof["verification_url"] == f"/api/compli402/proofs/{proof['proof_hash']}"


def test_execute_payment_failed(client):
    # A payment object with no reference fails mock verification.
    resp = client.post(
        "/api/compli402/execute",
        json=_intent(100.0, payment={"amount": 100.0}),
    )
    assert resp.status_code == 402
    data = resp.json()
    assert data["status"] == "PAYMENT_FAILED"
    assert data["proof"] is None


# ---------------------------------------------------------------------------
# proofs
# ---------------------------------------------------------------------------


def test_proofs_latest_and_by_hash(client):
    exec_resp = client.post(
        "/api/compli402/execute",
        json=_intent(100.0, payment={"reference": "pay-proof-1"}),
    )
    proof_hash = exec_resp.json()["proof"]["proof_hash"]

    latest = client.get("/api/compli402/proofs/latest")
    assert latest.status_code == 200
    assert latest.json()["proof_hash"] == proof_hash

    by_hash = client.get(f"/api/compli402/proofs/{proof_hash}")
    assert by_hash.status_code == 200
    assert by_hash.json()["proof_hash"] == proof_hash


def test_proof_not_found(client):
    resp = client.get("/api/compli402/proofs/does-not-exist")
    assert resp.status_code == 404
