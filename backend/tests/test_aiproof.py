"""Tests for AIProof bundle generation and deterministic hashing."""

from __future__ import annotations

from app.mvp2.proof.aiproof import build_aiproof, compute_proof_hash
from app.mvp2.schemas.aiproof import HASH_EXCLUDED_FIELDS, AIProofBundle

# The full set of fields an AIProof bundle must expose for the x402 challenge.
EXPECTED_FIELDS = {
    "proof_id",
    "proof_type",
    "actor_id",
    "actor_identity",
    "intent_id",
    "intent",
    "policy_id",
    "policy_version",
    "decision",
    "decision_reason",
    "execution_adapter",
    "execution_status",
    "payment_protocol",
    "payment_reference",
    "settlement_chain",
    "anchor_chain",
    "anchor_tx_id",
    "proof_hash",
    "created_at",
    "verification_url",
}


def _build(**overrides) -> AIProofBundle:
    kwargs = dict(
        actor_id="00000000-0000-0000-0000-000000000001",
        intent_id="11111111-1111-1111-1111-111111111111",
        decision="APPROVED",
        decision_reason=["APPROVED_BY_POLICY"],
        actor_identity={"name": "TravelAgent-01", "actor_type": "AGENT"},
        intent={"action": "book_flight", "amount": 100.0, "currency": "USDC"},
        policy_id="00000000-0000-0000-0000-000000000101",
        execution_adapter="x402",
        execution_status="CONFIRMED",
        payment_reference="pay-abc-123",
        settlement_chain="base-sepolia",
        created_at="2026-06-17T00:00:00+00:00",
        proof_id="proof-fixed-id",
    )
    kwargs.update(overrides)
    return build_aiproof(**kwargs)


# ---------------------------------------------------------------------------
# Schema completeness
# ---------------------------------------------------------------------------


def test_aiproof_bundle_exposes_all_required_fields() -> None:
    bundle = _build()
    assert set(bundle.model_dump().keys()) == EXPECTED_FIELDS


def test_aiproof_defaults() -> None:
    bundle = _build()
    assert bundle.proof_type == "compli402.execution"
    assert bundle.payment_protocol == "x402"
    assert bundle.anchor_chain == "algorand"
    # Post-hash fields are not set at build time.
    assert bundle.anchor_tx_id is None
    assert bundle.verification_url is None


# ---------------------------------------------------------------------------
# Deterministic hashing
# ---------------------------------------------------------------------------


def test_proof_hash_is_set_and_sha256() -> None:
    bundle = _build()
    assert bundle.proof_hash
    assert len(bundle.proof_hash) == 64
    assert all(c in "0123456789abcdef" for c in bundle.proof_hash)


def test_proof_hash_is_deterministic() -> None:
    first = _build()
    second = _build()
    assert first.proof_hash == second.proof_hash


def test_proof_hash_changes_with_content() -> None:
    base = _build()
    changed = _build(decision="DENIED")
    assert base.proof_hash != changed.proof_hash


def test_post_hash_fields_excluded_from_hash() -> None:
    bundle = _build()
    original_hash = bundle.proof_hash

    # Setting post-hash fields must NOT change the deterministic hash.
    bundle.anchor_tx_id = "TX-ANCHOR-999"
    bundle.verification_url = "/api/compli402/proofs/" + original_hash
    assert compute_proof_hash(bundle) == original_hash


def test_hash_excluded_fields_constant() -> None:
    assert HASH_EXCLUDED_FIELDS == frozenset(
        {"proof_hash", "anchor_tx_id", "verification_url"}
    )


def test_hashable_payload_omits_excluded_fields() -> None:
    bundle = _build()
    payload = bundle.hashable_payload()
    for field in HASH_EXCLUDED_FIELDS:
        assert field not in payload
    # Non-excluded fields remain present.
    assert payload["actor_id"] == bundle.actor_id
    assert payload["decision"] == "APPROVED"
