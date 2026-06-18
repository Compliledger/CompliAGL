"""Tests for the Algorand adapter integration wrapper.

These tests exercise the CompliAGL → shared-adapter field mapping and the
adapter-loading behaviour *without* requiring the shared
``compliledger-algorand-adapter`` to be installed.
"""

from __future__ import annotations

import pytest

from app.mvp2.anchor import algorand_adapter_service as svc


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


def _sample_bundle() -> dict:
    return {
        "actor_id": "actor-123",
        "intent_id": "intent-456",
        "decision": "APPROVED",
        "policy_version": "v3",
        "proof_hash": "abc123",
        "created_at": "2026-06-17T00:00:00Z",
        "decision_reason": ["WITHIN_LIMIT"],
        "reason_codes": ["FALLBACK"],
        "actor_identity": {"type": "AGENT"},
        "intent": {"action": "pay"},
        "execution_adapter": "x402",
        "payment_protocol": "x402",
        "payment_reference": "settled-001",
        "settlement_chain": "base-sepolia",
        "execution_status": "CONFIRMED",
    }


def test_mapping_constants_and_direct_fields() -> None:
    fields = svc._proof_schema_fields(_sample_bundle())

    assert fields["module_name"] == "CompliAGL"
    assert fields["state_type"] == "autonomous_execution"
    assert fields["decision_status"] == "APPROVED"
    assert fields["policy_version"] == "v3"
    assert fields["proof_snapshot_hash"] == "abc123"
    assert fields["timestamp"] == "2026-06-17T00:00:00Z"


def test_asset_id_prefers_actor_id() -> None:
    fields = svc._proof_schema_fields(_sample_bundle())
    assert fields["asset_id"] == "actor-123"


def test_asset_id_falls_back_to_intent_id() -> None:
    bundle = _sample_bundle()
    bundle["actor_id"] = None
    fields = svc._proof_schema_fields(bundle)
    assert fields["asset_id"] == "intent-456"


def test_reason_codes_prefers_decision_reason() -> None:
    fields = svc._proof_schema_fields(_sample_bundle())
    assert fields["reason_codes"] == ["WITHIN_LIMIT"]


def test_reason_codes_falls_back_to_reason_codes() -> None:
    bundle = _sample_bundle()
    bundle["decision_reason"] = None
    fields = svc._proof_schema_fields(bundle)
    assert fields["reason_codes"] == ["FALLBACK"]


def test_metadata_collects_execution_context() -> None:
    fields = svc._proof_schema_fields(_sample_bundle())
    assert fields["metadata"] == {
        "actor": {"type": "AGENT"},
        "intent": {"action": "pay"},
        "execution_adapter": "x402",
        "payment_protocol": "x402",
        "payment_reference": "settled-001",
        "settlement_chain": "base-sepolia",
        "x402_status": "CONFIRMED",
    }


def test_metadata_falls_back_to_legacy_keys() -> None:
    # Older AIProof bundles used ``actor`` and ``x402_status`` directly.
    bundle = {
        "actor_id": "actor-1",
        "intent_id": "intent-1",
        "decision": "APPROVED",
        "policy_version": "v1",
        "proof_hash": "h",
        "created_at": "2026-01-01T00:00:00Z",
        "reason_codes": ["X"],
        "actor": {"legacy": True},
        "execution_adapter": "x402",
        "x402_status": "CONFIRMED",
    }
    fields = svc._proof_schema_fields(bundle)
    assert fields["metadata"]["actor"] == {"legacy": True}
    assert fields["metadata"]["x402_status"] == "CONFIRMED"


def test_mapping_supports_object_bundles() -> None:
    class Bundle:
        actor_id = "actor-obj"
        intent_id = None
        decision = "DENIED"
        policy_version = "v1"
        proof_hash = "hash-obj"
        created_at = "2026-01-01T00:00:00Z"
        decision_reason = None
        reason_codes = ["X"]
        actor_identity = None
        actor = None
        intent = None
        execution_adapter = "mock"
        payment_protocol = "x402"
        payment_reference = None
        settlement_chain = None
        execution_status = None
        x402_status = None

    fields = svc._proof_schema_fields(Bundle())
    assert fields["asset_id"] == "actor-obj"
    assert fields["decision_status"] == "DENIED"
    assert fields["reason_codes"] == ["X"]
    assert fields["metadata"]["execution_adapter"] == "mock"


# ---------------------------------------------------------------------------
# Adapter loading / public API behaviour when adapter is absent
# ---------------------------------------------------------------------------


def _adapter_installed() -> bool:
    try:
        svc._load_adapter()
    except ImportError:
        return False
    return True


@pytest.mark.skipif(
    _adapter_installed(),
    reason="shared compliledger-algorand-adapter is installed",
)
def test_public_api_raises_helpful_error_without_adapter() -> None:
    bundle = _sample_bundle()
    for call in (
        lambda: svc.build_proof_schema_from_aiproof(bundle),
        lambda: svc.anchor_ai_proof_bundle(bundle),
        lambda: svc.verify_anchored_proof("actor-123"),
    ):
        with pytest.raises(ImportError, match="compliledger-algorand-adapter"):
            call()


def test_adapter_version_returns_string() -> None:
    assert isinstance(svc._adapter_version(), str)


# ---------------------------------------------------------------------------
# Mock anchoring (shared adapter stubbed out)
# ---------------------------------------------------------------------------


class _FakeAnchoredState:
    """Mimics the shared adapter's anchored-state return object."""

    def __init__(self) -> None:
        self.network = "algorand-testnet"
        self.proof_snapshot_hash = "abc123"
        self.txid = "TXMOCK123"
        self.explorer_url = "https://explorer.example/tx/TXMOCK123"
        self.anchored_at = "2026-06-17T00:00:00Z"


class _FakeProofSchema:
    """Stand-in for the shared adapter ``ProofSchema``."""

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.proof_snapshot_hash = kwargs.get("proof_snapshot_hash")


def test_anchor_ai_proof_bundle_mock(monkeypatch) -> None:
    """Anchoring delegates to the shared adapter and normalises its receipt."""
    captured: dict = {}

    def _fake_anchor(schema):
        captured["schema"] = schema
        return _FakeAnchoredState()

    def _fake_load_adapter():
        return _fake_anchor, None, _FakeProofSchema, None

    monkeypatch.setattr(svc, "_load_adapter", _fake_load_adapter)

    receipt = svc.anchor_ai_proof_bundle(_sample_bundle())

    # The bundle was mapped onto a ProofSchema and anchored.
    assert isinstance(captured["schema"], _FakeProofSchema)
    assert captured["schema"].kwargs["module_name"] == "CompliAGL"
    assert captured["schema"].kwargs["decision_status"] == "APPROVED"

    # Receipt is normalised into the CompliAGL anchor-receipt shape.
    assert receipt["chain"] == "algorand"
    assert receipt["network"] == "algorand-testnet"
    assert receipt["proof_hash"] == "abc123"
    assert receipt["txid"] == "TXMOCK123"
    assert receipt["explorer_url"] == "https://explorer.example/tx/TXMOCK123"
    assert receipt["anchored_at"] == "2026-06-17T00:00:00Z"
    assert receipt["adapter"] == svc.ADAPTER_DIST_NAME
