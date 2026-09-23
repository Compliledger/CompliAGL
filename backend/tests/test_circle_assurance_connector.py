"""Tests for CompliLedgerAssuranceConnector.

The connector never interprets what CompliLedger reports -- a healthy claim
and a degraded claim are both COLLECTED, content copied verbatim. Only
network/HTTP failures raise (docs/dev-rules.md rule 5).
"""

from __future__ import annotations

import httpx
import pytest

from app.services.evidence.connectors.base import (
    CollectRequest,
    ConnectorError,
    ConnectorTimeout,
)
from app.services.evidence.connectors.compliledger_assurance import (
    CIRCLE_ASSURANCE_ISSUER,
    CIRCLE_CONTROL_ID,
    CompliLedgerAssuranceConnector,
)
from app.utils.canonical_enums import EvidenceCollectionStatus

_REQUEST = CollectRequest(
    evidence_requirement_id="EV-CIRCLE-LUSD-ASSURANCE",
    evidence_type="compliledger.assurance_state.v1",
    source_type="EXTERNAL_APPLICATION",
)


def _connector(handler) -> CompliLedgerAssuranceConnector:
    return CompliLedgerAssuranceConnector(
        base_url="http://compliledger.test",
        http_client=httpx.Client(
            base_url="http://compliledger.test",
            transport=httpx.MockTransport(handler),
        ),
    )


def _control(**overrides):
    control = {
        "control_id": CIRCLE_CONTROL_ID,
        "applicability": "APPLICABLE",
        "result": "SATISFIED",
        "evidence_sufficiency": "SUFFICIENT",
        "evidence_freshness": "FRESH",
        "monitoring_status": "CURRENT",
        "assessment_id": "assessment-1",
        "decision_id": "decision-1",
        "proof_id": "proof-1",
        "proof_hash": "hash-1",
        "proof_status": "ACTIVE",
        "last_evaluated_at": "2026-09-23T00:00:00Z",
    }
    control.update(overrides)
    return control


def test_healthy_response_is_collected_verbatim():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["target_id"] == "target_lusd"
        assert request.url.params["control_ids"] == CIRCLE_CONTROL_ID
        return httpx.Response(
            200, json={"target_id": "target_lusd", "controls": [_control()]}
        )

    result = _connector(handler).collect(_REQUEST)
    assert result.status == EvidenceCollectionStatus.COLLECTED.value
    assert result.issuer == CIRCLE_ASSURANCE_ISSUER
    assert result.claims["result"] == "SATISFIED"
    assert result.claims["monitoring_status"] == "CURRENT"
    assert result.claims["control_id"] == CIRCLE_CONTROL_ID
    assert result.signature is None
    assert result.signature_valid is None


def test_degraded_response_is_collected_not_interpreted():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "target_id": "target_lusd",
                "controls": [
                    _control(result="NOT_EVALUABLE", monitoring_status="STALE")
                ],
            },
        )

    result = _connector(handler).collect(_REQUEST)
    assert result.status == EvidenceCollectionStatus.COLLECTED.value
    assert result.claims["result"] == "NOT_EVALUABLE"
    assert result.claims["monitoring_status"] == "STALE"


def test_missing_control_in_response_is_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"target_id": "target_lusd", "controls": []})

    result = _connector(handler).collect(_REQUEST)
    assert result.status == EvidenceCollectionStatus.NOT_FOUND.value
    assert result.error


def test_timeout_raises_connector_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ConnectorTimeout):
        _connector(handler).collect(_REQUEST)


def test_server_error_raises_connector_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    with pytest.raises(ConnectorError):
        _connector(handler).collect(_REQUEST)


def test_unreachable_raises_connector_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(ConnectorError):
        _connector(handler).collect(_REQUEST)
