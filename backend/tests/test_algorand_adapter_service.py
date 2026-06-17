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
        "actor": {"type": "AGENT"},
        "intent": {"action": "pay"},
        "execution_adapter": "x402",
        "payment_reference": "settled-001",
        "x402_status": "CONFIRMED",
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
        "payment_reference": "settled-001",
        "x402_status": "CONFIRMED",
    }


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
        actor = None
        intent = None
        execution_adapter = "mock"
        payment_reference = None
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
