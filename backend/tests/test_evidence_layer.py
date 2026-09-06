"""Tests for the production-grade evidence layer.

These cover the full pipeline — orchestration plan, connector collection,
validation, normalization and canonical packaging — and the required scenarios:

* valid identity delegation,
* expired evidence,
* stale allowance evidence,
* untrusted merchant source,
* target mismatch,
* connector timeout,
* partial connector failure,
* no silent mock fallback in production,
* deterministic normalized hashes,
* PII exclusion from public proof projections.

The connectors are generic and platform-neutral; nothing here assumes an airline
or a payment application.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.canonical.actor_identity import ActorIdentityCreate
from app.schemas.canonical.governance_package import (
    ExecutableGovernancePackageCreate,
)
from app.schemas.canonical.intent import IntentCreate
from app.schemas.canonical.operational_context import OperationalContextCreate
from app.schemas.canonical.policy_applicability import (
    ApplicabilityEvaluationCreate,
    PolicyResolutionCreate,
)
from app.schemas.canonical.target import TargetCreate
from app.services.canonical import (
    actor_identity_service,
    applicability_service,
    governance_package_service,
    intent_service,
    operational_context_service,
    policy_resolution_service,
    target_service,
)
from app.services.evidence import evidence_collection_service
from app.services.evidence.connectors import ConnectorRegistry
from app.services.evidence.connectors import simulators
from app.utils.timestamps import utc_now
from app.utils.canonical_enums import (
    CanonicalActorType,
    EvidenceCollectionStatus,
    EvidenceValidationOutcome,
    IntentType,
    SensitivityClassification,
    TargetType,
)

ORG = "org-evidence"

UTC = timezone.utc
ISSUED = datetime(2025, 1, 1, tzinfo=UTC)
FAR_FUTURE = datetime(2035, 1, 1, tzinfo=UTC)
PAST = datetime(2020, 1, 1, tzinfo=UTC)
# Long freshness so a fixed ISSUED date stays "fresh" and hashes stay stable.
LONG_FRESH = "P36500D"

# Evidence requirement ids used across the package.
EV_IDENTITY = "EV-IDENTITY"
EV_ALLOWANCE = "EV-ALLOWANCE"
EV_APPROVAL = "EV-APPROVAL"
EV_MERCHANT = "EV-MERCHANT"
EV_EXECUTION = "EV-EXECUTION"


# --------------------------------------------------------------------------- #
# Generic governance package (platform-neutral)
# --------------------------------------------------------------------------- #
def _requirements() -> list[dict]:
    return [
        {
            "requirement_id": "REQ-MAIN",
            "source_reference": "GEN §1",
            "normalized_text": "The action must satisfy governance evidence.",
            "requirement_type": "generic",
            "classification": "OBLIGATION",
            "mapped_control_ids": [
                "CTL-IDENTITY",
                "CTL-ALLOWANCE",
                "CTL-APPROVAL",
                "CTL-MERCHANT",
                "CTL-EXECUTION",
            ],
            "applicability_criteria": {
                "op": "equals",
                "field": "intent.action",
                "value": "perform_action",
            },
        }
    ]


def _controls() -> list[dict]:
    def ctl(cid, ev):
        return {
            "control_id": cid,
            "requirement_ids": ["REQ-MAIN"],
            "control_objective": f"Objective for {cid}.",
            "evaluation_expression": "True",
            "expected_outcome": "APPROVED",
            "mandatory": True,
            "severity": "HIGH",
            "failure_disposition": "DENY",
            "evidence_requirement_ids": [ev],
        }

    return [
        ctl("CTL-IDENTITY", EV_IDENTITY),
        ctl("CTL-ALLOWANCE", EV_ALLOWANCE),
        ctl("CTL-APPROVAL", EV_APPROVAL),
        ctl("CTL-MERCHANT", EV_MERCHANT),
        ctl("CTL-EXECUTION", EV_EXECUTION),
    ]


def _evidence() -> list[dict]:
    return [
        {
            "evidence_requirement_id": EV_IDENTITY,
            "control_ids": ["CTL-IDENTITY"],
            "evidence_type": "delegation",
            "authoritative_source_type": "identity_provider",
            "subject_binding": "actor",
            "freshness_requirement": LONG_FRESH,
            "validation_method": "signature_verification",
            "minimum_cardinality": 1,
            "mandatory": True,
            "allowed_issuers": ["idp.example"],
        },
        {
            "evidence_requirement_id": EV_ALLOWANCE,
            "control_ids": ["CTL-ALLOWANCE"],
            "evidence_type": "allowance",
            "authoritative_source_type": "account_state",
            "subject_binding": "actor",
            "freshness_requirement": "P1D",
            "minimum_cardinality": 1,
            "mandatory": True,
            "allowed_issuers": ["ledger.example"],
        },
        {
            "evidence_requirement_id": EV_APPROVAL,
            "control_ids": ["CTL-APPROVAL"],
            "evidence_type": "manager_approval",
            "authoritative_source_type": "approval_workflow",
            "subject_binding": "actor",
            "freshness_requirement": LONG_FRESH,
            "minimum_cardinality": 1,
            "mandatory": True,
            "allowed_issuers": ["approvals.example"],
        },
        {
            "evidence_requirement_id": EV_MERCHANT,
            "control_ids": ["CTL-MERCHANT"],
            "evidence_type": "vendor_approval",
            "authoritative_source_type": "external_application",
            "subject_binding": "target",
            "freshness_requirement": LONG_FRESH,
            "minimum_cardinality": 1,
            "mandatory": True,
            "allowed_issuers": ["procurement.example"],
        },
        {
            "evidence_requirement_id": EV_EXECUTION,
            "control_ids": ["CTL-EXECUTION"],
            "evidence_type": "execution_result",
            "authoritative_source_type": "execution_result",
            "subject_binding": "actor",
            "target_binding": "target",
            "freshness_requirement": LONG_FRESH,
            "minimum_cardinality": 1,
            "mandatory": True,
            "allowed_issuers": ["execution.example"],
        },
    ]


def _package_payload() -> ExecutableGovernancePackageCreate:
    return ExecutableGovernancePackageCreate(
        organization_id=ORG,
        package_name="generic-policy",
        package_version="1.0.0",
        requirements=_requirements(),
        control_definitions=_controls(),
        evidence_requirements=_evidence(),
        decision_conditions=[
            {
                "condition_id": "DC-1",
                "expression": "True",
                "resulting_decision": "APPROVED",
                "priority": 100,
                "reason_code": "OK",
                "terminal": True,
            }
        ],
        metadata={},
    )


def _publish(db):
    pkg = governance_package_service.create(db, _package_payload())
    result = governance_package_service.validate(db, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(
        db, ORG, pkg.id, approver_principal_id="tester", rationale="approved for test"
    )
    return governance_package_service.publish(db, ORG, pkg.id)


def _resolution(db, *, environment="STAGING"):
    """Publish a package and produce a fully-applicable policy resolution."""
    _publish(db)
    actor = actor_identity_service.create(
        db,
        ActorIdentityCreate(
            organization_id=ORG, actor_type=CanonicalActorType.AI_AGENT
        ),
    )
    intent = intent_service.create(
        db,
        IntentCreate(
            organization_id=ORG,
            intent_type=IntentType.WORKFLOW_ACTION,
            action="perform_action",
            actor_id=actor.id,
        ),
    )
    target = target_service.create(
        db,
        TargetCreate(
            organization_id=ORG,
            target_type=TargetType.MERCHANT,
            external_identifier="counterparty-01",
        ),
    )
    context = operational_context_service.create(
        db,
        OperationalContextCreate(
            organization_id=ORG, jurisdiction="US", environment=environment
        ),
    )
    resolution = policy_resolution_service.resolve(
        db,
        PolicyResolutionCreate(
            organization_id=ORG,
            actor_identity_id=actor.id,
            intent_id=intent.id,
            target_id=target.id,
            operational_context_id=context.id,
        ),
    )
    applicability_service.evaluate_for_resolution(
        db,
        ApplicabilityEvaluationCreate(
            organization_id=ORG, policy_resolution_id=resolution.id
        ),
    )
    return resolution, actor, target


# --------------------------------------------------------------------------- #
# Connector registry builders (mock simulators with controlled fixtures)
# --------------------------------------------------------------------------- #
def _base_fixtures(actor_id, target_id):
    """Fully-valid fixtures for every evidence requirement."""
    return {
        "identity": {
            EV_IDENTITY: {
                "issuer": "idp.example",
                "issued_at": ISSUED,
                "expires_at": FAR_FUTURE,
                "signature": "sig-identity",
                "signature_valid": True,
                "subject_id": actor_id,
                "claims": {"delegation": "granted", "scope": "perform_action"},
            }
        },
        "account": {
            EV_ALLOWANCE: {
                "issuer": "ledger.example",
                "issued_at": utc_now(),
                "expires_at": FAR_FUTURE,
                "subject_id": actor_id,
                "claims": {
                    "remaining": {"amount": "1000.00", "currency": "USD"}
                },
            }
        },
        "approval": {
            EV_APPROVAL: {
                "issuer": "approvals.example",
                "issued_at": ISSUED,
                "expires_at": FAR_FUTURE,
                "subject_id": actor_id,
                "claims": {"approved": True},
            }
        },
        "merchant": {
            EV_MERCHANT: {
                "issuer": "procurement.example",
                "issued_at": ISSUED,
                "expires_at": FAR_FUTURE,
                "subject_id": target_id,
                "claims": {"vendor_status": "approved"},
            }
        },
        "execution": {
            EV_EXECUTION: {
                "issuer": "execution.example",
                "issued_at": ISSUED,
                "expires_at": FAR_FUTURE,
                "subject_id": actor_id,
                "target_id": target_id,
                "claims": {"result": "confirmed"},
            }
        },
    }


def _registry(fixtures, *, is_mock=True) -> ConnectorRegistry:
    return ConnectorRegistry(
        [
            simulators.identity_delegation_connector(
                fixtures=fixtures["identity"], is_mock=is_mock
            ),
            simulators.account_allowance_connector(
                fixtures=fixtures["account"], is_mock=is_mock
            ),
            simulators.approval_connector(
                fixtures=fixtures["approval"], is_mock=is_mock
            ),
            simulators.external_application_connector(
                fixtures=fixtures["merchant"], is_mock=is_mock
            ),
            simulators.execution_result_connector(
                fixtures=fixtures["execution"], is_mock=is_mock
            ),
        ]
    )


def _run(db, resolution, registry, *, production_mode=False):
    return evidence_collection_service.start_collection(
        db,
        ORG,
        resolution.id,
        production_mode=production_mode,
        registry=registry,
    )


def _validation_by_req(db, job):
    from app.services.evidence import evidence_validation_service

    out = {}
    for v in evidence_validation_service.list_for_job(db, ORG, job.id):
        out[v.evidence_requirement_id] = v
    return out


def _normalized_by_req(db, job):
    from app.services.evidence import evidence_normalization_service

    out = {}
    for n in evidence_normalization_service.list_for_job(db, ORG, job.id):
        out[n.evidence_requirement_id] = n
    return out


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_valid_identity_delegation(db_session):
    resolution, actor, target = _resolution(db_session)
    registry = _registry(_base_fixtures(actor.id, target.external_identifier))
    outcome = _run(db_session, resolution, registry)

    validations = _validation_by_req(db_session, outcome.job)
    assert (
        validations[EV_IDENTITY].outcome
        == EvidenceValidationOutcome.VALID.value
    )
    normalized = _normalized_by_req(db_session, outcome.job)
    assert EV_IDENTITY in normalized
    norm = normalized[EV_IDENTITY]
    assert norm.subject == actor.id
    assert norm.source == "sim-identity-delegation"
    assert norm.issuer == "idp.example"
    assert norm.normalized_payload_hash

    # Evidence is collected from a connector — provenance proves it.
    raw = evidence_collection_service.list_raw_evidence(
        db_session, ORG, outcome.job.id
    )
    identity_raw = [r for r in raw if r.evidence_requirement_id == EV_IDENTITY][0]
    import json

    provenance = json.loads(identity_raw.provenance)
    assert provenance["collected_via"] == "connector"
    assert provenance["connector_id"] == "sim-identity-delegation"


def test_every_item_has_provenance_and_validation(db_session):
    resolution, actor, target = _resolution(db_session)
    registry = _registry(_base_fixtures(actor.id, target.external_identifier))
    outcome = _run(db_session, resolution, registry)

    raw = evidence_collection_service.list_raw_evidence(
        db_session, ORG, outcome.job.id
    )
    assert len(raw) == 5
    for item in raw:
        assert item.provenance and item.provenance != "{}"
        assert item.source_id and item.source_type

    validations = _validation_by_req(db_session, outcome.job)
    # Every raw item receives exactly one validation result.
    assert len(validations) == 5

    # The canonical package is generated and complete.
    import json

    assert outcome.package.evaluation_id == resolution.id
    assert json.loads(outcome.package.missing_evidence) == []
    assert json.loads(outcome.package.invalid_evidence) == []
    assert len(json.loads(outcome.package.normalized_evidence_references)) == 5
    assert outcome.package.package_hash


def test_expired_evidence(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    fixtures["approval"][EV_APPROVAL]["expires_at"] = PAST
    registry = _registry(fixtures)
    outcome = _run(db_session, resolution, registry)

    validations = _validation_by_req(db_session, outcome.job)
    assert (
        validations[EV_APPROVAL].outcome
        == EvidenceValidationOutcome.EXPIRED.value
    )
    # Expired evidence is never normalized and is surfaced as invalid + missing.
    normalized = _normalized_by_req(db_session, outcome.job)
    assert EV_APPROVAL not in normalized
    import json

    invalid = json.loads(outcome.package.invalid_evidence)
    assert any(i["evidence_requirement_id"] == EV_APPROVAL for i in invalid)
    missing = json.loads(outcome.package.missing_evidence)
    assert any(m["evidence_requirement_id"] == EV_APPROVAL for m in missing)


def test_stale_allowance_evidence(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    # Allowance has a P1D freshness window; a 2020 issue date is stale.
    fixtures["account"][EV_ALLOWANCE]["issued_at"] = PAST
    fixtures["account"][EV_ALLOWANCE]["expires_at"] = FAR_FUTURE
    registry = _registry(fixtures)
    outcome = _run(db_session, resolution, registry)

    validations = _validation_by_req(db_session, outcome.job)
    assert (
        validations[EV_ALLOWANCE].outcome
        == EvidenceValidationOutcome.STALE.value
    )


def test_untrusted_merchant_source(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    # Issuer not in the requirement's allowed issuers => untrusted source.
    fixtures["merchant"][EV_MERCHANT]["issuer"] = "rogue.example"
    registry = _registry(fixtures)
    outcome = _run(db_session, resolution, registry)

    validations = _validation_by_req(db_session, outcome.job)
    assert (
        validations[EV_MERCHANT].outcome
        == EvidenceValidationOutcome.UNTRUSTED_SOURCE.value
    )


def test_target_mismatch(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    # Execution evidence binds to the wrong target.
    fixtures["execution"][EV_EXECUTION]["target_id"] = "wrong-target"
    registry = _registry(fixtures)
    outcome = _run(db_session, resolution, registry)

    validations = _validation_by_req(db_session, outcome.job)
    assert (
        validations[EV_EXECUTION].outcome
        == EvidenceValidationOutcome.TARGET_MISMATCH.value
    )


def test_connector_timeout(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    fixtures["approval"][EV_APPROVAL] = {"behavior": "timeout"}
    registry = _registry(fixtures)
    outcome = _run(db_session, resolution, registry)

    import json

    failures = json.loads(outcome.job.failures)
    approval_failures = [
        f for f in failures if f["evidence_requirement_id"] == EV_APPROVAL
    ]
    assert approval_failures
    assert (
        approval_failures[0]["status"]
        == EvidenceCollectionStatus.TIMEOUT.value
    )
    # The retry policy was applied (default 3 attempts).
    assert approval_failures[0]["attempts"] == 3
    assert outcome.job.status == EvidenceCollectionStatus.PARTIAL.value


def test_retry_then_success(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    # Fail the first two attempts, succeed on the third.
    fixtures["approval"][EV_APPROVAL]["fail_times"] = 2
    registry = _registry(fixtures)
    outcome = _run(db_session, resolution, registry)

    validations = _validation_by_req(db_session, outcome.job)
    assert (
        validations[EV_APPROVAL].outcome
        == EvidenceValidationOutcome.VALID.value
    )
    assert outcome.job.status == EvidenceCollectionStatus.COMPLETED.value


def test_partial_connector_failure(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    fixtures["merchant"][EV_MERCHANT] = {"behavior": "error", "error": "boom"}
    registry = _registry(fixtures)
    outcome = _run(db_session, resolution, registry)

    assert outcome.job.status == EvidenceCollectionStatus.PARTIAL.value
    # The other four items still collected and normalized.
    normalized = _normalized_by_req(db_session, outcome.job)
    assert EV_MERCHANT not in normalized
    assert {EV_IDENTITY, EV_ALLOWANCE, EV_APPROVAL, EV_EXECUTION} <= set(
        normalized
    )


def test_no_silent_mock_fallback_in_production(db_session):
    resolution, actor, target = _resolution(db_session, environment="PRODUCTION")
    registry = _registry(_base_fixtures(actor.id, target.external_identifier), is_mock=True)
    # production_mode omitted -> derived from the PRODUCTION context.
    outcome = _run(db_session, resolution, registry, production_mode=None)

    assert outcome.job.production_mode is True
    raw = evidence_collection_service.list_raw_evidence(
        db_session, ORG, outcome.job.id
    )
    assert raw, "raw evidence records should still be written explicitly"
    for item in raw:
        assert (
            item.collection_status
            == EvidenceCollectionStatus.REJECTED_MOCK.value
        )
        assert item.payload is None
    # No fabricated/normalized evidence; the package is explicitly incomplete.
    normalized = _normalized_by_req(db_session, outcome.job)
    assert normalized == {}
    import json

    assert json.loads(outcome.package.missing_evidence)


def test_production_allows_real_connectors(db_session):
    resolution, actor, target = _resolution(db_session, environment="PRODUCTION")
    # Non-mock connectors are accepted in production mode.
    registry = _registry(_base_fixtures(actor.id, target.external_identifier), is_mock=False)
    outcome = _run(db_session, resolution, registry, production_mode=None)

    assert outcome.job.production_mode is True
    assert outcome.job.status == EvidenceCollectionStatus.COMPLETED.value
    normalized = _normalized_by_req(db_session, outcome.job)
    assert len(normalized) == 5


def test_deterministic_normalized_hashes(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)

    reg1 = _registry(fixtures)
    out1 = _run(db_session, resolution, reg1)
    hashes1 = {
        r: n.normalized_payload_hash
        for r, n in _normalized_by_req(db_session, out1.job).items()
    }

    reg2 = _registry(fixtures)
    out2 = _run(db_session, resolution, reg2)
    hashes2 = {
        r: n.normalized_payload_hash
        for r, n in _normalized_by_req(db_session, out2.job).items()
    }

    assert hashes1 == hashes2
    assert all(hashes1.values())


def test_monetary_values_normalized_to_minor_units(db_session):
    resolution, actor, target = _resolution(db_session)
    registry = _registry(_base_fixtures(actor.id, target.external_identifier))
    outcome = _run(db_session, resolution, registry)

    import json

    norm = _normalized_by_req(db_session, outcome.job)[EV_ALLOWANCE]
    claims = json.loads(norm.normalized_claims)
    # "1000.00" USD -> 100000 integer minor units (no float).
    assert claims["remaining"] == {"amount_minor": 100000, "currency": "USD"}


def test_pii_excluded_from_public_projections(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    # The identity source returns a PII-laden payload but publishes only
    # non-PII claims for normalization.
    fixtures["identity"][EV_IDENTITY]["sensitivity"] = (
        SensitivityClassification.PII.value
    )
    fixtures["identity"][EV_IDENTITY]["payload"] = {
        "full_name": "Jane Q. Public",
        "national_id": "123-45-6789",
    }
    fixtures["identity"][EV_IDENTITY]["claims"] = {"delegation": "granted"}
    registry = _registry(fixtures)
    outcome = _run(db_session, resolution, registry)

    import json

    raw = evidence_collection_service.list_raw_evidence(
        db_session, ORG, outcome.job.id
    )
    identity_raw = [
        r for r in raw if r.evidence_requirement_id == EV_IDENTITY
    ][0]
    # Sensitive payload is held by secure reference, never stored inline.
    assert identity_raw.payload is None
    assert identity_raw.payload_reference
    assert identity_raw.payload_hash

    # The normalized projection and package carry no PII, only claims + hashes.
    norm = _normalized_by_req(db_session, outcome.job)[EV_IDENTITY]
    normalized_blob = norm.normalized_claims
    assert "national_id" not in normalized_blob
    assert "Jane" not in normalized_blob

    package_refs = json.dumps(
        json.loads(outcome.package.normalized_evidence_references)
    )
    assert "national_id" not in package_refs
    assert "Jane" not in package_refs
    # Only the hash of the sensitive payload is projected.
    assert norm.source_payload_hash == identity_raw.payload_hash


def test_unresolved_when_no_connector(db_session):
    resolution, actor, target = _resolution(db_session)
    fixtures = _base_fixtures(actor.id, target.external_identifier)
    # Registry lacks the execution-result connector entirely.
    registry = ConnectorRegistry(
        [
            simulators.identity_delegation_connector(
                fixtures=fixtures["identity"]
            ),
            simulators.account_allowance_connector(
                fixtures=fixtures["account"]
            ),
            simulators.approval_connector(fixtures=fixtures["approval"]),
            simulators.external_application_connector(
                fixtures=fixtures["merchant"]
            ),
        ]
    )
    outcome = _run(db_session, resolution, registry)

    import json

    unresolved = json.loads(outcome.plan.unresolved)
    assert any(
        u["evidence_requirement_id"] == EV_EXECUTION
        and u["reason"] == "NO_AUTHORITATIVE_CONNECTOR"
        for u in unresolved
    )
    # And it surfaces as missing in the package — never silently satisfied.
    missing = json.loads(outcome.package.missing_evidence)
    assert any(m["evidence_requirement_id"] == EV_EXECUTION for m in missing)
