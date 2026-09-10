"""Tests for the HarborStone SENTRY sanctions-screening connector.

The connector is real (runs on the production collection path, returns a
structured integrity-hashed item); only the screening *lookup* is a fixed
demo dataset. These tests pin:

* the deterministic dataset (wallet_001 -> NO_MATCH, wallet_002 ->
  POTENTIAL_MATCH, wallet_003 -> CONFIRMED_MATCH, unknown -> NO_MATCH),
* the full ``demo3.sanctions-screening.v1`` claims shape + a verifiable
  ``integrity_hash``,
* that it validates ``VALID`` against the real HarborStone evidence
  requirement, so the mandatory control can be evaluated,
* that it is registered **by default** (no env-gate) and is not a mock.
"""

from __future__ import annotations

import json
import logging

from app.db.harborstone_package import (
    EV_SCREENING,
    SCREENING_EVIDENCE_TYPE,
    SCREENING_ISSUER,
)
from app.services.evidence import evidence_validation_service
from app.services.evidence.connectors.base import CollectRequest
from app.services.evidence.connectors.harborstone_sentry_screening import (
    HarborStoneSentryScreeningConnector,
    harborstone_sentry_screening_connector,
)
from app.services.evidence.connectors.production import default_production_registry
from app.models.raw_evidence import RawEvidence
from app.utils.canonical_enums import (
    EvidenceCollectionStatus,
    EvidenceSourceType,
    EvidenceValidationOutcome,
)
from app.utils.hashing import hash_dict, sha256_hash
from app.utils.timestamps import utc_now

_CONNECTOR_ID = "harborstone-sentry-sanctions-screening"
_FRESHNESS = "P7D"


def _request(screened: str | None) -> CollectRequest:
    return CollectRequest(
        evidence_requirement_id=EV_SCREENING,
        evidence_type=SCREENING_EVIDENCE_TYPE,
        source_type=EvidenceSourceType.EXTERNAL_APPLICATION.value,
        subject_id=screened,
        target_id=screened,
        intent_id="intent-xyz",
        allowed_issuers=[SCREENING_ISSUER],
        freshness_threshold=_FRESHNESS,
    )


def _raw_from_result(result, *, screened: str) -> RawEvidence:
    """Build a RawEvidence the way evidence_orchestration_service does, for the
    fields evidence_validation_service.evaluate() reads."""
    claims = result.claims or {}
    provenance = {
        "connector_trusted_issuers": [SCREENING_ISSUER],
        "signature_valid": result.signature_valid,
        "revoked": bool(result.revoked),
        "source_authority": bool(result.source_authority),
        "requirement": {
            "allowed_issuers": [SCREENING_ISSUER],
            "freshness_threshold": _FRESHNESS,
            "expected_subject_id": screened,
            "expected_target_id": None,
            "expected_intent_id": None,
        },
    }
    return RawEvidence(
        organization_id="harborstone-demo",
        evidence_requirement_id=EV_SCREENING,
        source_id=_CONNECTOR_ID,
        source_type=EvidenceSourceType.EXTERNAL_APPLICATION.value,
        subject_id=result.subject_id,
        target_id=result.target_id,
        intent_id=result.intent_id,
        issued_at=result.issued_at,
        expires_at=result.expires_at,
        payload=None,
        payload_reference=None,
        payload_hash=hash_dict({"claims": claims}),
        claims=json.dumps(claims),
        issuer=result.issuer,
        signature=result.signature,
        provenance=json.dumps(provenance),
        collection_status=result.status,
    )


# --------------------------------------------------------------------------- #
def test_dataset_is_deterministic():
    conn = HarborStoneSentryScreeningConnector()
    cases = {
        "wallet_001": ("NO_MATCH", 0, "LOW", False),
        "wallet_002": ("POTENTIAL_MATCH", 1, "HIGH", True),
        "wallet_003": ("CONFIRMED_MATCH", 2, "CRITICAL", True),
        "0.0.3": ("NO_MATCH", 0, "LOW", False),
        "never-heard-of-this-one": ("NO_MATCH", 0, "LOW", False),
    }
    for screened, (result, count, risk, review) in cases.items():
        claims = conn.collect(_request(screened)).claims
        assert claims["result"] == result, screened
        assert claims["match_count"] == count
        assert claims["risk_level"] == risk
        assert claims["requires_human_review"] is review
        # same input -> byte-identical verdict fields on a second call
        again = conn.collect(_request(screened)).claims
        assert again["result"] == result and again["screening_id"] == claims["screening_id"]


def test_claims_carry_the_full_contract_and_are_labelled_simulation():
    claims = HarborStoneSentryScreeningConnector().collect(
        _request("wallet_002")
    ).claims
    for key in (
        "schema_version", "screening_id", "tenant_id", "case_id",
        "correlation_id", "requesting_agent_id", "screening_agent_id",
        "subject", "scope", "screening_source", "screened_at", "result",
        "match_count", "risk_level", "requires_human_review", "evidence_refs",
        "integrity_hash",
    ):
        assert key in claims, key
    assert claims["schema_version"] == "demo3.sanctions-screening.v1"
    assert claims["scope"] == "SANCTIONS_SCREENING_ONLY"
    assert claims["screening_source"] == "DEMO_SANCTIONS_SOURCE"
    assert claims["subject"] == {"type": "wallet", "id": "wallet_002"}
    assert claims["simulation"] is True
    assert "SIMULATED" in claims["simulation_note"]
    assert claims["correlation_id"] == "corr_intent-xyz"


def test_integrity_hash_is_real_and_verifiable():
    claims = HarborStoneSentryScreeningConnector().collect(
        _request("wallet_003")
    ).claims
    recomputed = sha256_hash(
        json.dumps(
            {k: v for k, v in claims.items() if k != "integrity_hash"},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    assert claims["integrity_hash"] == recomputed


def test_collect_echoes_bindings_and_logs_simulation(caplog):
    with caplog.at_level(logging.INFO):
        result = HarborStoneSentryScreeningConnector().collect(
            _request("wallet_001")
        )
    assert result.status == EvidenceCollectionStatus.COLLECTED.value
    assert result.issuer == SCREENING_ISSUER
    assert result.subject_id == "wallet_001"
    assert result.target_id == "wallet_001"
    assert result.intent_id == "intent-xyz"
    assert result.signature_valid is True
    assert any("SIMULATED sanctions screening" in r.message for r in caplog.records)


def test_standin_item_validates_as_valid():
    result = HarborStoneSentryScreeningConnector().collect(_request("wallet_001"))
    verdict = evidence_validation_service.evaluate(
        _raw_from_result(result, screened="wallet_001")
    )
    assert verdict["outcome"] == EvidenceValidationOutcome.VALID.value, verdict


def test_registered_by_default_and_not_mock(monkeypatch):
    # No env var of any kind is needed.
    monkeypatch.delenv("COMPLIAGL_HARBORSTONE_SCREENING_PLACEHOLDER", raising=False)
    registry = default_production_registry()

    conn = registry.get(_CONNECTOR_ID)
    assert isinstance(conn, HarborStoneSentryScreeningConnector)
    assert conn.is_mock is False

    selected = registry.select_authoritative(
        EvidenceSourceType.EXTERNAL_APPLICATION.value, SCREENING_EVIDENCE_TYPE
    )
    assert selected is conn


def test_factory_matches_class():
    assert isinstance(
        harborstone_sentry_screening_connector(),
        HarborStoneSentryScreeningConnector,
    )
