"""Tests for the ExecutableGovernancePackage integration contract.

Covers the CompliLedger -> CompliAGL package lifecycle (ingest, validate,
approve, publish, retrieve, supersede, retire), published-package immutability,
source traceability, deterministic decision conditions, the deterministic
interpreter, JSON-schema validation, signature verification, and API authz.
"""

from __future__ import annotations

import json
import os

import pytest

from app.schemas.canonical.package_json_schema import validate_package_document
from app.services.canonical.package_interpreter import (
    DeterministicPackageInterpreter,
    ExpressionError,
    evaluate_expression,
)

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "travel_policy_package.json"
)

ORG = "org-travel"
AUTHOR_HDR = {"X-Organization-Id": ORG, "X-Governance-Role": "COMPLILEDGER_SERVICE"}
READ_HDR = {"X-Organization-Id": ORG}


def _fixture() -> dict:
    with open(FIXTURE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------- #
# JSON Schema + traceability validation
# --------------------------------------------------------------------------- #
def test_fixture_passes_contract_validation():
    document = _fixture()
    assert validate_package_document(document) == []


def test_requirement_without_source_reference_is_rejected():
    document = _fixture()
    document["requirements"][0]["source_reference"] = ""
    errors = validate_package_document(document)
    assert any("source_reference" in e for e in errors)


def test_control_referencing_unknown_requirement_is_rejected():
    document = _fixture()
    document["control_definitions"][0]["requirement_ids"] = ["REQ-UNKNOWN"]
    errors = validate_package_document(document)
    assert any("unknown requirement" in e for e in errors)


def test_evidence_requirement_must_map_to_control():
    document = _fixture()
    document["evidence_requirements"][0]["control_ids"] = ["CTL-UNKNOWN"]
    errors = validate_package_document(document)
    assert any("unknown control" in e for e in errors)


def test_package_without_decision_conditions_is_rejected():
    document = _fixture()
    document["decision_conditions"] = []
    errors = validate_package_document(document)
    assert any("decision_conditions" in e for e in errors)


# --------------------------------------------------------------------------- #
# Deterministic interpreter
# --------------------------------------------------------------------------- #
def _package():
    return {"decision_conditions": _fixture()["decision_conditions"]}


def _base_context(**overrides):
    ctx = {
        "airline": "Delta",
        "approved_airlines": ["Delta", "United"],
        "origin": "SFO",
        "destination": "JFK",
        "approved_locations": ["SFO", "JFK"],
        "is_international": False,
        "prior_authorization": False,
        "cabin_class": "ECONOMY",
        "fare_minor": 50000,
        "manager_approval": False,
    }
    ctx.update(overrides)
    return ctx


def test_interpreter_approves_compliant_booking():
    result = DeterministicPackageInterpreter().interpret(_package(), _base_context())
    assert result.decision == "APPROVED"
    assert result.reason_codes == ["WITHIN_TRAVEL_POLICY"]


def test_interpreter_denies_unapproved_airline():
    result = DeterministicPackageInterpreter().interpret(
        _package(), _base_context(airline="Spirit")
    )
    assert result.decision == "DENIED"
    assert result.reason_codes == ["AIRLINE_NOT_APPROVED"]


def test_interpreter_escalates_over_fare_cap_without_approval():
    result = DeterministicPackageInterpreter().interpret(
        _package(), _base_context(fare_minor=90000)
    )
    assert result.decision == "ESCALATED"
    assert result.reason_codes == ["FARE_EXCEEDS_LIMIT_REQUIRES_APPROVAL"]


def test_interpreter_approves_over_fare_cap_with_manager_approval():
    result = DeterministicPackageInterpreter().interpret(
        _package(), _base_context(fare_minor=90000, manager_approval=True)
    )
    assert result.decision == "APPROVED"


def test_interpreter_escalates_international_without_authorization():
    result = DeterministicPackageInterpreter().interpret(
        _package(), _base_context(is_international=True)
    )
    assert result.decision == "ESCALATED"
    assert result.reason_codes == ["INTERNATIONAL_REQUIRES_AUTHORIZATION"]


def test_interpreter_is_deterministic():
    interp = DeterministicPackageInterpreter()
    ctx = _base_context(fare_minor=90000)
    first = interp.interpret(_package(), ctx)
    second = interp.interpret(_package(), ctx)
    assert first == second


def test_interpreter_fails_closed_on_no_match():
    # A package whose only condition never matches -> default DENIED.
    package = {
        "decision_conditions": [
            {
                "condition_id": "X",
                "expression": "airline == 'nonexistent'",
                "resulting_decision": "APPROVED",
                "priority": 1,
                "reason_code": "SHOULD_NOT_MATCH",
                "terminal": True,
            }
        ]
    }
    result = DeterministicPackageInterpreter().interpret(package, _base_context())
    assert result.decision == "DENIED"
    assert result.reason_codes == ["NO_CONDITION_MATCHED"]


def test_expression_evaluator_rejects_arbitrary_code():
    with pytest.raises(ExpressionError):
        evaluate_expression("__import__('os').system('echo hi')", {})


def test_expression_evaluator_supports_membership_and_logic():
    ctx = {"airline": "Delta", "approved": ["Delta"], "amt": 10}
    assert evaluate_expression("airline in approved and amt < 20", ctx) is True
    assert evaluate_expression("airline not in approved", ctx) is False


# --------------------------------------------------------------------------- #
# API lifecycle
# --------------------------------------------------------------------------- #
def _create_via_api(api_client, body=None):
    resp = api_client.post(
        "/api/v1/governance-packages", json=body or _fixture(), headers=AUTHOR_HDR
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_full_package_lifecycle_via_api(api_client):
    created = _create_via_api(api_client)
    assert created["status"] == "DRAFT"
    assert created["package_hash"]
    pid = created["id"]

    # Validate
    val = api_client.post(
        f"/api/v1/governance-packages/{pid}/validate", headers=READ_HDR
    )
    assert val.status_code == 200, val.text
    assert val.json()["valid"] is True

    got = api_client.get(
        f"/api/v1/governance-packages/{pid}", headers=READ_HDR
    ).json()
    assert got["status"] == "VALIDATED"

    # Approve
    appr = api_client.post(
        f"/api/v1/governance-packages/{pid}/approve",
        json={"approved_by": "admin@corp"},
        headers=AUTHOR_HDR,
    )
    assert appr.status_code == 200, appr.text
    assert appr.json()["status"] == "APPROVED"
    assert appr.json()["approved_by"] == "admin@corp"

    # Publish
    pub = api_client.post(
        f"/api/v1/governance-packages/{pid}/publish", json={}, headers=AUTHOR_HDR
    )
    assert pub.status_code == 200, pub.text
    assert pub.json()["status"] == "PUBLISHED"
    assert pub.json()["published_at"] is not None

    # Retrieve the published version by name+version filter
    listing = api_client.get(
        "/api/v1/governance-packages",
        params={"package_name": "corporate-travel-policy", "status": "PUBLISHED"},
        headers=READ_HDR,
    )
    assert listing.status_code == 200
    assert any(p["id"] == pid for p in listing.json())


def test_cannot_publish_unapproved_package(api_client):
    created = _create_via_api(api_client)
    pid = created["id"]
    # Skip validate/approve — publish must be rejected.
    resp = api_client.post(
        f"/api/v1/governance-packages/{pid}/publish", json={}, headers=AUTHOR_HDR
    )
    assert resp.status_code == 409


def test_published_package_is_immutable_no_update_route(api_client):
    created = _create_via_api(api_client)
    pid = created["id"]
    # There is deliberately no PATCH/PUT endpoint for packages.
    resp = api_client.patch(
        f"/api/v1/governance-packages/{pid}",
        json={"package_name": "hacked"},
        headers=AUTHOR_HDR,
    )
    assert resp.status_code == 405


def test_invalid_package_validation_returns_422(api_client):
    body = _fixture()
    # Valid shape (passes Pydantic) but broken traceability: the control maps to
    # a requirement that does not exist in the package.
    body["control_definitions"][0]["requirement_ids"] = ["REQ-DOES-NOT-EXIST"]
    created = _create_via_api(api_client, body)
    pid = created["id"]
    resp = api_client.post(
        f"/api/v1/governance-packages/{pid}/validate", headers=READ_HDR
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["valid"] is False
    assert detail["errors"]


def test_create_requires_authorized_role(api_client):
    resp = api_client.post(
        "/api/v1/governance-packages",
        json=_fixture(),
        headers={"X-Organization-Id": ORG},  # no governance role
    )
    assert resp.status_code == 403


def test_governance_admin_role_may_create(api_client):
    resp = api_client.post(
        "/api/v1/governance-packages",
        json=_fixture(),
        headers={"X-Organization-Id": ORG, "X-Governance-Role": "GOVERNANCE_ADMIN"},
    )
    assert resp.status_code == 201


def _publish(api_client, body=None):
    created = _create_via_api(api_client, body)
    pid = created["id"]
    api_client.post(
        f"/api/v1/governance-packages/{pid}/validate", headers=READ_HDR
    )
    api_client.post(
        f"/api/v1/governance-packages/{pid}/approve",
        json={"approved_by": "admin@corp"},
        headers=AUTHOR_HDR,
    )
    pub = api_client.post(
        f"/api/v1/governance-packages/{pid}/publish", json={}, headers=AUTHOR_HDR
    )
    assert pub.status_code == 200, pub.text
    return pub.json()


def test_supersede_published_package(api_client):
    v1 = _publish(api_client)

    v2_body = _fixture()
    v2_body["package_version"] = "1.1.0"
    v2_body["supersedes_package_id"] = v1["id"]
    v2 = _publish(api_client, v2_body)

    # v1 must now be SUPERSEDED and point at v2.
    v1_reloaded = api_client.get(
        f"/api/v1/governance-packages/{v1['id']}", headers=READ_HDR
    ).json()
    assert v1_reloaded["status"] == "SUPERSEDED"
    assert v1_reloaded["superseded_by_package_id"] == v2["id"]


def test_explicit_supersede_endpoint(api_client):
    v1 = _publish(api_client)
    v2_body = _fixture()
    v2_body["package_version"] = "2.0.0"
    v2 = _publish(api_client, v2_body)

    resp = api_client.post(
        f"/api/v1/governance-packages/{v1['id']}/supersede",
        json={"superseded_by_package_id": v2["id"]},
        headers=AUTHOR_HDR,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "SUPERSEDED"


def test_retire_published_package(api_client):
    v1 = _publish(api_client)
    resp = api_client.post(
        f"/api/v1/governance-packages/{v1['id']}/retire", headers=AUTHOR_HDR
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "RETIRED"


def test_duplicate_published_name_version_is_rejected(api_client):
    _publish(api_client)
    # Ingesting a second package with the same name+version while one is
    # published must be refused.
    resp = api_client.post(
        "/api/v1/governance-packages", json=_fixture(), headers=AUTHOR_HDR
    )
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# Signature verification (service layer)
# --------------------------------------------------------------------------- #
def test_publish_rejects_invalid_signature_when_signing_configured(
    db_session, monkeypatch
):
    from app.core.config import settings
    from app.schemas.canonical.governance_package import (
        ExecutableGovernancePackageCreate,
    )
    from app.services.canonical import governance_package_service as svc
    from app.services.canonical.errors import PackageSignatureError

    monkeypatch.setattr(
        settings, "GOVERNANCE_SIGNING_KEYS", {"key-1": "s3cr3t"}, raising=False
    )

    body = _fixture()
    body["signer_key_id"] = "key-1"
    body["signature"] = "deadbeef"  # wrong signature
    pkg = svc.create(db_session, ExecutableGovernancePackageCreate(**body))
    svc.validate(db_session, ORG, pkg.id)
    svc.approve(db_session, ORG, pkg.id, "admin@corp")
    with pytest.raises(PackageSignatureError):
        svc.publish(db_session, ORG, pkg.id)


def test_publish_accepts_valid_signature(db_session, monkeypatch):
    from app.core.config import settings
    from app.schemas.canonical.governance_package import (
        ExecutableGovernancePackageCreate,
    )
    from app.services.canonical import governance_package_service as svc
    from app.services.canonical.package_signing import compute_signature

    monkeypatch.setattr(
        settings, "GOVERNANCE_SIGNING_KEYS", {"key-1": "s3cr3t"}, raising=False
    )

    body = _fixture()
    body["signer_key_id"] = "key-1"
    pkg = svc.create(db_session, ExecutableGovernancePackageCreate(**body))
    svc.validate(db_session, ORG, pkg.id)
    svc.approve(db_session, ORG, pkg.id, "admin@corp")
    # Sign the (now-bound) package hash and attach it.
    pkg.signature = compute_signature("key-1", pkg.package_hash)
    db_session.commit()

    published = svc.publish(db_session, ORG, pkg.id)
    assert published.status == "PUBLISHED"


def test_published_content_hash_is_stable(db_session):
    from app.schemas.canonical.governance_package import (
        ExecutableGovernancePackageCreate,
    )
    from app.services.canonical import governance_package_service as svc

    pkg = svc.create(db_session, ExecutableGovernancePackageCreate(**_fixture()))
    svc.validate(db_session, ORG, pkg.id)
    hash_before = pkg.package_hash
    svc.approve(db_session, ORG, pkg.id, "admin@corp")
    published = svc.publish(db_session, ORG, pkg.id)
    # Publishing recomputes and verifies the hash; content unchanged -> stable.
    assert published.package_hash == hash_before


def test_runtime_retrieves_only_published_version(db_session):
    from app.schemas.canonical.governance_package import (
        ExecutableGovernancePackageCreate,
    )
    from app.services.canonical import governance_package_service as svc

    pkg = svc.create(db_session, ExecutableGovernancePackageCreate(**_fixture()))
    # Not yet published -> runtime lookup returns nothing.
    assert (
        svc.get_published_version(
            db_session, ORG, "corporate-travel-policy", "1.0.0"
        )
        is None
    )
    svc.validate(db_session, ORG, pkg.id)
    svc.approve(db_session, ORG, pkg.id, "admin@corp")
    svc.publish(db_session, ORG, pkg.id)
    found = svc.get_published_version(
        db_session, ORG, "corporate-travel-policy", "1.0.0"
    )
    assert found is not None
    assert found.id == pkg.id
