"""End-to-end: the real HarborStone package + the real SENTRY screening
connector drive the deterministic pipeline to the right decision.

This is the regression guard for the two CompliAegis adversarial tactics that
used to ERROR because the screening evidence type had no connector over HTTP
(the mandatory control failed closed -> DENIED):

* clean screen (NO_MATCH), sub-threshold  -> APPROVED
* confirmed match                          -> DENIED
* potential match (requires human review)  -> ESCALATED

The screening *lookup* is the connector's fixed demo dataset; everything else
here -- publish, resolve, collect, validate, normalize, control eval,
assessment, decision -- is the real pipeline. The authority-context call is
faked (sufficient) so the test isolates the screening signal.
"""

from __future__ import annotations

import json

import pytest

from app.db import seed
from app.db.harborstone_package import (
    PACKAGE_NAME,
    PACKAGE_VERSION,
    build_harborstone_package,
)
from app.schemas.canonical.actor_identity import ActorIdentityCreate
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
    assessment_service,
    authority_context_service,
    control_evaluation_service,
    decision_service,
    evidence_sufficiency_service,
    governance_package_service,
    intent_service,
    operational_context_service,
    policy_resolution_service,
    target_service,
)
from app.services.canonical.authority_context_service import AuthorityContext
from app.services.evidence import evidence_collection_service
from app.services.evidence.connectors import ConnectorRegistry
from app.services.evidence.connectors.harborstone_sentry_screening import (
    harborstone_sentry_screening_connector,
)
from app.utils.canonical_enums import (
    CanonicalActorType,
    DecisionOutcome,
    IntentType,
    TargetType,
)

ORG = "harborstone-demo"
_SUB_THRESHOLD = 24_999_999  # one minor unit below the $250K escalation line


@pytest.fixture()
def published_package(db_session):
    seed.seed_organizations(db_session)
    pkg = governance_package_service.create(
        db_session, build_harborstone_package(ORG)
    )
    result = governance_package_service.validate(db_session, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(
        db_session, ORG, pkg.id,
        approver_principal_id="tester", rationale="approved for test",
    )
    governance_package_service.publish(db_session, ORG, pkg.id)
    return pkg


@pytest.fixture(autouse=True)
def _sufficient_authority(monkeypatch):
    ctx = AuthorityContext(
        status="OK",
        sufficient=True,
        permission_present=True,
        approval_required=False,
        findings=("permission_present",),
    )
    monkeypatch.setattr(
        authority_context_service, "default_client", lambda **kw: _Client(ctx)
    )


class _Client:
    def __init__(self, ctx):
        self._ctx = ctx

    def fetch(self, **kwargs):
        return self._ctx


def _decide(db, *, counterparty: str, amount_minor: int = _SUB_THRESHOLD):
    actor = actor_identity_service.create(
        db,
        ActorIdentityCreate(
            organization_id=ORG,
            actor_type=CanonicalActorType.AI_AGENT,
            wallet_or_agent_account_id="agent-aira",
        ),
    )
    intent = intent_service.create(
        db,
        IntentCreate(
            organization_id=ORG,
            intent_type=IntentType.PAYMENT,
            action="propose",
            actor_id=actor.id,
            amount_minor=amount_minor,
            amount_currency="USD",
            parameters={
                "compliidentity_resource": "aml.action",
                "compliidentity_action": "propose",
                "compliidentity_resource_instance": "HARBORSTONE-2024-0042",
            },
        ),
    )
    target = target_service.create(
        db,
        TargetCreate(
            organization_id=ORG,
            target_type=TargetType.TRANSACTION,
            external_identifier=counterparty,
        ),
    )
    context = operational_context_service.create(
        db,
        OperationalContextCreate(
            organization_id=ORG, jurisdiction="US", environment="STAGING"
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
    evidence_collection_service.start_collection(
        db,
        ORG,
        resolution.id,
        production_mode=True,
        registry=ConnectorRegistry([harborstone_sentry_screening_connector()]),
    )
    evidence_sufficiency_service.evaluate_for_resolution(db, ORG, resolution.id)
    control_evaluation_service.evaluate_for_resolution(db, ORG, resolution.id)
    assessment = assessment_service.assess_for_resolution(db, ORG, resolution.id)
    decision = decision_service.decide_for_resolution(db, ORG, resolution.id)
    return assessment, decision


def test_clean_screen_sub_threshold_is_approved(db_session, published_package):
    assessment, decision = _decide(db_session, counterparty="wallet_001")
    assert assessment.overall_result == "SATISFIED"
    assert decision.outcome == DecisionOutcome.APPROVED.value


def test_confirmed_match_is_denied(db_session, published_package):
    assessment, decision = _decide(db_session, counterparty="wallet_003")
    assert assessment.overall_result == "NOT_SATISFIED"
    assert decision.outcome == DecisionOutcome.DENIED.value
    assert "SANCTIONS_CONFIRMED_MATCH" in json.loads(decision.reason_codes)


def test_potential_match_is_escalated(db_session, published_package):
    assessment, decision = _decide(db_session, counterparty="wallet_002")
    assert assessment.overall_result == "NOT_SATISFIED"
    assert decision.outcome == DecisionOutcome.ESCALATED.value
    assert "SANCTIONS_HUMAN_REVIEW_REQUIRED" in json.loads(decision.reason_codes)


def test_unknown_counterparty_defaults_to_clean_screen(db_session, published_package):
    # The CompliAegis harness screens recipient "0.0.3" -> not in the dataset
    # -> NO_MATCH -> the sanctioned path still authorizes.
    _assessment, decision = _decide(db_session, counterparty="0.0.3")
    assert decision.outcome == DecisionOutcome.APPROVED.value


def test_screening_evidence_reaches_the_decision_context(db_session, published_package):
    # The normalized screening claims are surfaced to decision conditions.
    _assessment, decision = _decide(db_session, counterparty="wallet_002")
    triggered = json.loads(decision.decision_conditions_triggered)
    assert any(
        t["condition_id"] == "DC-HARBORSTONE-SANCTIONS-REVIEW" for t in triggered
    )
