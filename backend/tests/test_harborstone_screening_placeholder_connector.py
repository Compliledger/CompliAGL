"""Tests for the HarborStone PLACEHOLDER sanctions-screening connector.

This connector screens nothing -- it returns a hardcoded stand-in so the
HarborStone package's placeholder control chain can run end to end over HTTP
(see ``PENDING_REVIEW_harborstone_screening_control_placeholder.md``). These
tests pin the two things that matter:

* the stand-in item it returns validates as ``VALID`` against the real
  HarborStone evidence requirement (issuer, freshness, signature, bindings),
  so the mandatory control can reach SATISFIED;
* it is registered **only** when ``COMPLIAGL_HARBORSTONE_SCREENING_PLACEHOLDER``
  holds the exact acknowledgement string -- never by default, never on a
  merely-truthy value.
"""

from __future__ import annotations

import json
import logging

from app.services.evidence.connectors.base import CollectRequest
from app.services.evidence.connectors.harborstone_screening_placeholder import (
    HARBORSTONE_SCREENING_PLACEHOLDER_EVIDENCE_TYPE,
    HARBORSTONE_SCREENING_PLACEHOLDER_ISSUER,
    HarborStoneScreeningPlaceholderConnector,
    harborstone_screening_placeholder_connector,
)
from app.services.evidence.connectors.production import default_production_registry
from app.services.evidence import evidence_validation_service
from app.models.raw_evidence import RawEvidence
from app.utils.canonical_enums import (
    EvidenceCollectionStatus,
    EvidenceSourceType,
    EvidenceValidationOutcome,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now

_ENV_VAR = "COMPLIAGL_HARBORSTONE_SCREENING_PLACEHOLDER"
_ACK = "stand-in-not-real-screening"
_CONNECTOR_ID = "harborstone-sanctions-screening-placeholder"

# The real HarborStone requirement (app/db/harborstone_package.py).
_REQ_ID = "EV-PLACEHOLDER-SANCTIONS-SCREENING"
_ALLOWED_ISSUERS = ["harborstone-screening-placeholder.example"]
_FRESHNESS = "P36500D"


def _request() -> CollectRequest:
    return CollectRequest(
        evidence_requirement_id=_REQ_ID,
        evidence_type=HARBORSTONE_SCREENING_PLACEHOLDER_EVIDENCE_TYPE,
        source_type=EvidenceSourceType.EXTERNAL_APPLICATION.value,
        subject_id="actor-identity-1",
        target_id="HARBORSTONE-2024-0042",
        intent_id="intent-1",
        allowed_issuers=list(_ALLOWED_ISSUERS),
        freshness_threshold=_FRESHNESS,
    )


def _raw_from_result(result) -> RawEvidence:
    """Build a RawEvidence the way evidence_orchestration_service._persist_raw_evidence
    does, for the fields evidence_validation_service.evaluate() reads."""
    claims = result.claims or {}
    payload_hash = hash_dict({"claims": claims})
    provenance = {
        "connector_trusted_issuers": [HARBORSTONE_SCREENING_PLACEHOLDER_ISSUER],
        "signature_valid": result.signature_valid,
        "revoked": bool(result.revoked),
        "source_authority": bool(result.source_authority),
        "requirement": {
            "allowed_issuers": list(_ALLOWED_ISSUERS),
            "freshness_threshold": _FRESHNESS,
            "expected_subject_id": "actor-identity-1",
            "expected_target_id": "HARBORSTONE-2024-0042",
            "expected_intent_id": None,
        },
    }
    return RawEvidence(
        organization_id="harborstone-demo",
        evidence_requirement_id=_REQ_ID,
        source_id=_CONNECTOR_ID,
        source_type=EvidenceSourceType.EXTERNAL_APPLICATION.value,
        subject_id=result.subject_id,
        target_id=result.target_id,
        intent_id=result.intent_id,
        issued_at=result.issued_at,
        expires_at=result.expires_at,
        payload=None,
        payload_reference=None,
        payload_hash=payload_hash,
        claims=json.dumps(claims),
        issuer=result.issuer,
        signature=result.signature,
        provenance=json.dumps(provenance),
        collection_status=result.status,
    )


def test_collect_returns_labelled_standin(caplog):
    connector = HarborStoneScreeningPlaceholderConnector()
    assert connector.is_mock is False

    with caplog.at_level(logging.WARNING):
        result = connector.collect(_request())

    assert result.status == EvidenceCollectionStatus.COLLECTED.value
    assert result.issuer == HARBORSTONE_SCREENING_PLACEHOLDER_ISSUER
    assert result.claims["placeholder"] is True
    assert result.claims["screening_result"] == "STANDIN_PASS"
    assert "placeholder" in result.signature.lower()
    assert "not-a-real-attestation" in result.signature.lower()
    # request bindings are echoed back so validation's binding checks pass
    assert result.subject_id == "actor-identity-1"
    assert result.target_id == "HARBORSTONE-2024-0042"
    assert result.intent_id == "intent-1"
    # every collect() is loud about being a stand-in
    assert any(
        "NOT a real screening result" in r.message or "STAND-IN" in r.message
        for r in caplog.records
    )


def test_standin_item_validates_as_valid():
    """The item must reach VALID or the mandatory control can never be SATISFIED."""
    result = HarborStoneScreeningPlaceholderConnector().collect(_request())
    verdict = evidence_validation_service.evaluate(_raw_from_result(result))
    assert verdict["outcome"] == EvidenceValidationOutcome.VALID.value, verdict


def test_not_registered_by_default(monkeypatch):
    monkeypatch.delenv(_ENV_VAR, raising=False)
    registry = default_production_registry()
    assert registry.get(_CONNECTOR_ID) is None
    assert (
        registry.select_authoritative(
            EvidenceSourceType.EXTERNAL_APPLICATION.value,
            HARBORSTONE_SCREENING_PLACEHOLDER_EVIDENCE_TYPE,
        )
        is None
    )


def test_not_registered_on_merely_truthy_value(monkeypatch):
    for value in ("1", "true", "yes", "on"):
        monkeypatch.setenv(_ENV_VAR, value)
        assert default_production_registry().get(_CONNECTOR_ID) is None


def test_registered_only_on_exact_acknowledgement(monkeypatch):
    monkeypatch.setenv(_ENV_VAR, _ACK)
    registry = default_production_registry()

    connector = registry.get(_CONNECTOR_ID)
    assert isinstance(connector, HarborStoneScreeningPlaceholderConnector)

    selected = registry.select_authoritative(
        EvidenceSourceType.EXTERNAL_APPLICATION.value,
        HARBORSTONE_SCREENING_PLACEHOLDER_EVIDENCE_TYPE,
    )
    assert selected is connector


def test_factory_matches_class():
    assert isinstance(
        harborstone_screening_placeholder_connector(),
        HarborStoneScreeningPlaceholderConnector,
    )
