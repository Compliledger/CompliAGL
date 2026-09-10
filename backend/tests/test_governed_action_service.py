"""``governed_action_service.propose`` runs the real intent -> decision pipeline.

Mirrors ``test_harborstone_screening_pipeline`` but exercises the single
orchestration entry point the Astra ``propose_governed_action`` tool uses, and
asserts the invariants that matter for that tool: a Decision is always
produced, and nothing downstream of it (approval, authorization) happens
implicitly.
"""

from __future__ import annotations

import json

import pytest

from app.db import seed
from app.db.harborstone_package import build_harborstone_package
from app.services.canonical import authority_context_service, governance_package_service
from app.services.canonical import governed_action_service
from app.services.canonical.authority_context_service import AuthorityContext
from app.services.evidence.connectors import ConnectorRegistry
from app.services.evidence.connectors.harborstone_sentry_screening import (
    harborstone_sentry_screening_connector,
)
from app.repositories.canonical import (
    ExecutionAuthorizationRepository,
    IntentRepository,
)
from app.utils.canonical_enums import DecisionOutcome, IntentType

ORG = "harborstone-demo"
CASE = "HARBORSTONE-2024-0042"
_SUB_THRESHOLD = 24_999_999
_AT_THRESHOLD = 25_000_000


@pytest.fixture()
def published_package(db_session):
    seed.seed_organizations(db_session)
    seed.seed_harborstone_actors(db_session)
    pkg = governance_package_service.create(db_session, build_harborstone_package(ORG))
    result = governance_package_service.validate(db_session, ORG, pkg.id)
    assert result.valid, result.errors
    governance_package_service.approve(
        db_session, ORG, pkg.id,
        approver_principal_id="tester", rationale="approved for test",
    )
    governance_package_service.publish(db_session, ORG, pkg.id)
    return pkg


class _Client:
    def __init__(self, ctx):
        self._ctx = ctx

    def fetch(self, **kwargs):
        return self._ctx


@pytest.fixture()
def _authority(monkeypatch):
    def _install(ctx):
        monkeypatch.setattr(
            authority_context_service, "default_client", lambda **kw: _Client(ctx)
        )

    return _install


def _propose(db, *, amount_minor, counterparty="wallet_001"):
    return governed_action_service.propose(
        db,
        ORG,
        actor_id=seed.HARBORSTONE_AIRA_ACTOR_ID,
        intent_type=IntentType.TRANSFER,
        action="astra_transfer",
        compliidentity_resource="aml.action",
        compliidentity_action="propose",
        resource_instance=CASE,
        target_identifier=counterparty,
        rationale="review complete",
        amount_minor=amount_minor,
        amount_currency="USD",
        registry=ConnectorRegistry([harborstone_sentry_screening_connector()]),
    )


def test_clean_screen_sub_threshold_approves(db_session, published_package, _authority):
    _authority(AuthorityContext(status="OK", sufficient=True, permission_present=True,
                                approval_required=False, findings=("permission_present",)))
    result = _propose(db_session, amount_minor=_SUB_THRESHOLD)

    assert result.decision.outcome == DecisionOutcome.APPROVED.value
    assert result.assessment.overall_result == "SATISFIED"
    assert result.intent.id and result.policy_resolution.id
    # Nothing downstream happened implicitly.
    assert not ExecutionAuthorizationRepository(db_session).list_for_intent(
        ORG, result.intent.id
    )


def test_at_threshold_escalates(db_session, published_package, _authority):
    _authority(AuthorityContext(status="OK", sufficient=False, permission_present=True,
                                approval_required=True, findings=("approval_required",)))
    result = _propose(db_session, amount_minor=_AT_THRESHOLD)
    assert result.decision.outcome == DecisionOutcome.ESCALATED.value
    assert "HUMAN_APPROVAL_REQUIRED" in json.loads(result.decision.reason_codes)


def test_confirmed_match_denies(db_session, published_package, _authority):
    _authority(AuthorityContext(status="OK", sufficient=True, permission_present=True,
                                approval_required=False, findings=("permission_present",)))
    result = _propose(db_session, amount_minor=_SUB_THRESHOLD, counterparty="wallet_003")
    assert result.decision.outcome == DecisionOutcome.DENIED.value


def test_intent_carries_compliidentity_probe_params(db_session, published_package, _authority):
    _authority(AuthorityContext(status="OK", sufficient=True, permission_present=True,
                                approval_required=False, findings=("permission_present",)))
    result = _propose(db_session, amount_minor=_SUB_THRESHOLD)
    intent = IntentRepository(db_session).get(ORG, result.intent.id)
    params = json.loads(intent.parameters)
    assert params["compliidentity_resource"] == "aml.action"
    assert params["compliidentity_action"] == "propose"
    assert params["compliidentity_resource_instance"] == CASE
