"""Tests for the canonical CompliAGL AIProof subsystem.

Covers canonicalization (RFC 8785 JCS), deterministic hashing, digital signing,
independent local verification, schema validation/publication, the full
governance-lifecycle coverage, evidence-by-reference (no embedded payloads), the
CompliLedger handoff, and the v1 AIProof API.
"""

from __future__ import annotations

import pytest

from app.schemas.canonical.aiproof import (
    AIPROOF_SCHEMA_VERSION,
    ActorIdentityRef,
    AIProof,
    AIProofStatus,
    AssessmentRef,
    CanonicalEvidencePackageRef,
    DecisionRef,
    EvidenceReference,
    EvidenceSufficiencyRef,
    ExecutionAuthorizationRef,
    ExternalExecutionResultRef,
    FindingRef,
    GovernancePackageRef,
    GovernedOutcome,
    HandoffStatus,
    IntentRef,
    OperationalContextRef,
    PolicyResolutionRef,
    ProofMetadata,
    ProofTimestamps,
    RemediationLineage,
    TargetRef,
)
from app.services.canonical.aiproof import (
    build_aiproof,
    canonicalize,
    generate_signed_aiproof,
    sha256_hex,
    sign_aiproof,
    verify_aiproof,
)
from app.services.canonical.aiproof.canonicalization import (
    CANONICALIZATION_ALGORITHM,
    HASH_ALGORITHM,
)
from app.services.canonical.aiproof.handoff import (
    LocalCompliLedgerHandoff,
    build_handoff_payload,
)
from app.services.canonical.aiproof.json_schema import (
    aiproof_json_schema,
    validate_against_schema,
)


# --------------------------------------------------------------------------- #
# Fixtures / builders
# --------------------------------------------------------------------------- #
def _minimal_content(**overrides):
    content = dict(
        metadata=ProofMetadata(
            aiproof_id="proof-1",
            organization_id="org-1",
            governance_evaluation_id="eval-1",
            correlation_id="corr-1",
            governed_outcome=GovernedOutcome.APPROVED_AND_EXECUTED,
        ),
        actor_identity=ActorIdentityRef(
            actor_identity_id="actor-1",
            actor_type="AI_AGENT",
            verification_status="VERIFIED",
            actor_hash="hash-actor",
        ),
        intent=IntentRef(
            intent_id="intent-1",
            action="book_flight",
            amount_minor=10000,
            amount_currency="USDC",
            intent_hash="hash-intent",
        ),
        decision=DecisionRef(
            decision_id="decision-1",
            outcome="APPROVED",
            reason_codes=["APPROVED_BY_POLICY"],
            engine_version="decision-engine/1.0",
            decision_hash="hash-decision",
        ),
        timestamps=ProofTimestamps(generated_at="2026-08-02T00:00:00+00:00"),
        engine_versions={"decision_engine": "1.0"},
    )
    content.update(overrides)
    return content


def _full_lifecycle_content():
    """Content exercising every governance-lifecycle projection."""
    content = _minimal_content(
        target=TargetRef(target_id="t1", target_type="MERCHANT", trust_status="TRUSTED"),
        operational_context=OperationalContextRef(
            operational_context_id="ctx-1", environment="PRODUCTION",
            context_hash="hash-ctx",
        ),
        governance_packages=[
            GovernancePackageRef(package_id="pkg-1", package_version="1.2.0",
                                 package_hash="hash-pkg")
        ],
        policy_resolution=PolicyResolutionRef(
            policy_resolution_id="pr-1", status="RESOLVED",
            selected_package_ids=["pkg-1"], result_hash="hash-pr",
        ),
        assessment=AssessmentRef(assessment_id="as-1", overall_result="SATISFIED",
                                 assessment_hash="hash-as"),
        evidence_references=[
            EvidenceReference(
                evidence_id="ev-1", evidence_hash="hash-ev",
                source_type="IDENTITY_PROVIDER", source_classification="PII",
                validation_outcome="VALID",
                secure_retrieval_reference="vault://evidence/ev-1",
            )
        ],
        canonical_evidence_package=CanonicalEvidencePackageRef(
            canonical_evidence_package_id="cep-1", evidence_package_hash="hash-cep",
        ),
        evidence_sufficiency=EvidenceSufficiencyRef(
            evidence_sufficiency_id="es-1", overall_result="SUFFICIENT",
            result_hash="hash-es",
        ),
        findings=[FindingRef(finding_id="f-1", finding_type="CONTROL_FAILURE",
                             severity="HIGH", status="OPEN", finding_hash="hash-f")],
        remediation_lineage=RemediationLineage(
            remediation_plan_ids=["rp-1"], resolution_evidence_ids=["re-1"],
            resolved_finding_ids=["f-1"], resolved_by_decision_id="decision-1",
        ),
        execution_authorization=ExecutionAuthorizationRef(
            execution_authorization_id="auth-1", status="CONSUMED",
            authorization_hash="hash-auth",
        ),
        external_execution_result=ExternalExecutionResultRef(
            external_execution_result_id="xr-1", adapter="x402", status="CONFIRMED",
            external_reference="tx-abc", settlement_chain="base-sepolia",
        ),
    )
    return content


# --------------------------------------------------------------------------- #
# Canonicalization (RFC 8785)
# --------------------------------------------------------------------------- #
def test_canonicalization_sorts_keys_and_is_compact():
    assert canonicalize({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert canonicalize([1, "x", True, None]) == '[1,"x",true,null]'


def test_canonicalization_escapes_control_characters():
    assert canonicalize({"k": "a\nb\t\"c\""}) == '{"k":"a\\nb\\t\\"c\\""}'


def test_canonicalization_rejects_non_finite_numbers():
    with pytest.raises(ValueError):
        canonicalize(float("inf"))


def test_sha256_hex_is_stable_and_order_independent():
    assert sha256_hex({"a": 1, "b": 2}) == sha256_hex({"b": 2, "a": 1})


# --------------------------------------------------------------------------- #
# Build / hash / sign
# --------------------------------------------------------------------------- #
def test_build_sets_hash_and_algorithms_but_not_signature():
    proof = build_aiproof(**_minimal_content())
    assert proof.status == AIProofStatus.GENERATED
    assert proof.canonicalization_algorithm == CANONICALIZATION_ALGORITHM
    assert proof.hash_algorithm == HASH_ALGORITHM
    assert proof.aiproof_hash and len(proof.aiproof_hash) == 64
    assert proof.signature is None
    assert proof.component_hashes  # populated


def test_hash_is_deterministic():
    assert build_aiproof(**_minimal_content()).aiproof_hash == (
        build_aiproof(**_minimal_content()).aiproof_hash
    )


def test_hash_changes_with_content():
    base = build_aiproof(**_minimal_content())
    changed = build_aiproof(
        **_minimal_content(
            decision=DecisionRef(decision_id="decision-1", outcome="DENIED",
                                 decision_hash="hash-decision"),
        )
    )
    assert base.aiproof_hash != changed.aiproof_hash


def test_status_change_does_not_change_hash():
    proof = build_aiproof(**_minimal_content())
    original = proof.aiproof_hash
    proof.status = AIProofStatus.SUPERSEDED
    from app.services.canonical.aiproof.generator import compute_aiproof_hash

    assert compute_aiproof_hash(proof) == original


def test_sign_sets_signature_and_status():
    proof = sign_aiproof(build_aiproof(**_minimal_content()))
    assert proof.signature
    assert proof.signer_key_id
    assert proof.status == AIProofStatus.SIGNED


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
def test_verify_valid_proof():
    proof = generate_signed_aiproof(**_full_lifecycle_content())
    result = verify_aiproof(proof)
    assert result.valid
    assert result.schema_valid and result.hash_valid
    assert result.component_hashes_valid and result.signature_valid
    assert result.algorithms_recognized
    assert result.errors == []


def test_verify_detects_tampered_content():
    proof = generate_signed_aiproof(**_minimal_content())
    payload = proof.model_dump(mode="json")
    payload["decision"]["outcome"] = "DENIED"
    result = verify_aiproof(payload)
    assert not result.valid
    assert not result.hash_valid


def test_verify_detects_bad_signature():
    proof = generate_signed_aiproof(**_minimal_content())
    proof.signature = "0" * 64
    result = verify_aiproof(proof)
    assert not result.valid
    assert not result.signature_valid


# --------------------------------------------------------------------------- #
# Lifecycle coverage
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("outcome", list(GovernedOutcome))
def test_all_governed_outcomes_supported(outcome):
    content = _minimal_content()
    content["metadata"].governed_outcome = outcome
    proof = generate_signed_aiproof(**content)
    assert verify_aiproof(proof).valid
    assert proof.metadata.governed_outcome == outcome


def test_full_lifecycle_projections_present_and_hashed():
    proof = generate_signed_aiproof(**_full_lifecycle_content())
    for component in (
        "metadata", "actor_identity", "intent", "target", "operational_context",
        "governance_packages", "policy_resolution", "assessment",
        "evidence_references", "canonical_evidence_package", "evidence_sufficiency",
        "decision", "findings", "remediation_lineage", "execution_authorization",
        "external_execution_result", "timestamps",
    ):
        assert component in proof.component_hashes, component


# --------------------------------------------------------------------------- #
# Evidence is referenced, never embedded
# --------------------------------------------------------------------------- #
def test_evidence_is_referenced_not_embedded():
    proof = generate_signed_aiproof(**_full_lifecycle_content())
    ref = proof.evidence_references[0]
    # Only id/hash/classification/outcome/retrieval-reference — no payload field.
    assert set(ref.model_dump(exclude_none=True)) <= {
        "evidence_id", "evidence_hash", "evidence_type", "source_id",
        "source_type", "source_classification", "validation_outcome",
        "secure_retrieval_reference",
    }
    assert "payload" not in ref.model_dump()


def test_evidence_reference_forbids_extra_payload_fields():
    with pytest.raises(Exception):
        EvidenceReference(evidence_id="e1", payload={"pan": "4111111111111111"})


# --------------------------------------------------------------------------- #
# JSON Schema publication
# --------------------------------------------------------------------------- #
def test_published_schema_validates_proof():
    proof = generate_signed_aiproof(**_full_lifecycle_content())
    assert validate_against_schema(proof.model_dump(mode="json")) == []


def test_published_schema_is_versioned():
    schema = aiproof_json_schema()
    assert schema["x-aiproof-schema-version"] == AIPROOF_SCHEMA_VERSION
    assert schema["$id"].endswith("aiproof.schema.json")


def test_schema_rejects_missing_required_fields():
    errors = validate_against_schema({"status": "GENERATED"})
    assert errors


# --------------------------------------------------------------------------- #
# CompliLedger handoff
# --------------------------------------------------------------------------- #
def test_build_handoff_payload_carries_verification_material():
    proof = generate_signed_aiproof(**_full_lifecycle_content())
    handoff = build_handoff_payload(proof, requested_proof_policy="standard")
    assert handoff.aiproof_id == "proof-1"
    assert handoff.schema_version == AIPROOF_SCHEMA_VERSION
    assert handoff.aiproof_hash == proof.aiproof_hash
    assert handoff.signature == proof.signature
    assert handoff.signer_key_id == proof.signer_key_id
    # Privacy classification derives from the most restrictive evidence source.
    assert handoff.privacy_classification == "PII"
    assert handoff.correlation_id == "corr-1"


def test_handoff_requires_signed_proof():
    proof = build_aiproof(**_minimal_content())  # unsigned
    with pytest.raises(ValueError):
        build_handoff_payload(proof)


def test_local_handoff_accepts_valid_proof():
    proof = generate_signed_aiproof(**_minimal_content())
    handoff = build_handoff_payload(proof)
    result = LocalCompliLedgerHandoff().submit(handoff)
    assert result.status == HandoffStatus.ACCEPTED
    assert result.reference


def test_local_handoff_rejects_tampered_proof():
    proof = generate_signed_aiproof(**_minimal_content())
    handoff = build_handoff_payload(proof)
    # Tamper with the canonical proof carried in the handoff.
    handoff.canonical_aiproof.decision.outcome = "DENIED"
    result = LocalCompliLedgerHandoff().submit(handoff)
    assert result.status == HandoffStatus.REJECTED


# --------------------------------------------------------------------------- #
# API + persistence
# --------------------------------------------------------------------------- #
def _api_generate_body():
    proof = generate_signed_aiproof(**_full_lifecycle_content())
    body = proof.model_dump(mode="json")
    for field in ("status", "canonicalization_algorithm", "hash_algorithm",
                  "issuer", "signer_key_id", "aiproof_hash", "signature",
                  "component_hashes"):
        body.pop(field, None)
    return body


def test_api_generate_retrieve_verify_submit(api_client):
    headers = {"X-Organization-Id": "org-1"}
    body = _api_generate_body()

    created = api_client.post("/api/v1/aiproofs", json=body)
    assert created.status_code == 201, created.text
    proof = created.json()
    aiproof_id = proof["metadata"]["aiproof_id"]
    assert proof["signature"]
    assert proof["status"] == "SIGNED"

    got = api_client.get(f"/api/v1/aiproofs/{aiproof_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["aiproof_hash"] == proof["aiproof_hash"]

    verified = api_client.post(
        f"/api/v1/aiproofs/{aiproof_id}/verify", headers=headers
    )
    assert verified.status_code == 200
    assert verified.json()["valid"] is True

    submitted = api_client.post(
        f"/api/v1/aiproofs/{aiproof_id}/submit", headers=headers, json={}
    )
    assert submitted.status_code == 200
    assert submitted.json()["result_status"] == "ACCEPTED"

    handoff = api_client.get(
        f"/api/v1/aiproofs/{aiproof_id}/handoff", headers=headers
    )
    assert handoff.status_code == 200
    assert handoff.json()["status"] == "ACCEPTED_BY_COMPLILEDGER"
    assert handoff.json()["handoff_status"] == "ACCEPTED"


def test_api_history_filters_by_intent(api_client):
    headers = {"X-Organization-Id": "org-1"}
    api_client.post("/api/v1/aiproofs", json=_api_generate_body())

    history = api_client.get(
        "/api/v1/aiproofs/history", headers=headers, params={"intent_id": "intent-1"}
    )
    assert history.status_code == 200
    items = history.json()
    assert len(items) == 1
    assert items[0]["intent_id"] == "intent-1"
    assert items[0]["governed_outcome"] == "APPROVED_AND_EXECUTED"

    empty = api_client.get(
        "/api/v1/aiproofs/history", headers=headers, params={"intent_id": "nope"}
    )
    assert empty.json() == []


def test_api_schema_endpoint(api_client):
    resp = api_client.get("/api/v1/aiproofs/schema")
    assert resp.status_code == 200
    assert resp.json()["x-aiproof-schema-version"] == AIPROOF_SCHEMA_VERSION


def test_api_retrieve_unknown_returns_404(api_client):
    resp = api_client.get(
        "/api/v1/aiproofs/does-not-exist", headers={"X-Organization-Id": "org-1"}
    )
    assert resp.status_code == 404


def test_api_tenant_isolation(api_client):
    api_client.post("/api/v1/aiproofs", json=_api_generate_body())
    # Different tenant cannot retrieve the proof.
    resp = api_client.get(
        "/api/v1/aiproofs/proof-1", headers={"X-Organization-Id": "other-org"}
    )
    assert resp.status_code == 404
