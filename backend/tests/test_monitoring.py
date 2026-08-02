"""Continuous monitoring & automated re-evaluation tests.

Covers the required demonstration scenarios and the acceptance criteria:

* changes trigger impact analysis,
* affected authorizations can be invalidated,
* re-evaluation creates new immutable records,
* historical decisions and proofs remain available,
* proof supersession is visible and verifiable.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.models.decision import Decision
from app.models.execution_authorization import ExecutionAuthorization
from app.models.governance_evaluation import GovernanceEvaluation
from app.models.intent import Intent
from app.repositories.canonical import (
    CanonicalAIProofRepository,
    DecisionRepository,
    ExecutionAuthorizationRepository,
)
from app.services.canonical.aiproof import generator
from app.services.canonical.aiproof import service as aiproof_service
from app.services.canonical.aiproof.verify import verify_aiproof
from app.services.canonical.monitoring import (
    monitoring_service,
    proof_supersession,
    reevaluation_job,
    supersession_service,
)
from app.services.canonical.monitoring.change_detector import (
    StateHashChangeDetector,
    compute_state_hash,
    get_detector,
)
from app.utils.canonical_enums import (
    AuthorizationStatus,
    DecisionOutcome,
    DecisionSupersessionStatus,
    MonitoringChangeType,
    ReevaluationStatus,
)

ORG = "org-monitor"


def _seed_governed_intent(db, *, org: str = ORG) -> SimpleNamespace:
    """Create an APPROVED + authorized intent with an initial signed AIProof."""
    suffix = uuid.uuid4().hex[:8]
    actor_id = f"actor-{suffix}"
    intent = Intent(
        organization_id=org,
        intent_type="PAYMENT",
        action="book_flight",
        requested_outcome="ticket_issued",
        actor_id=actor_id,
        amount_minor=25000,
        amount_currency="USD",
    )
    db.add(intent)
    db.flush()

    evaluation = GovernanceEvaluation(
        organization_id=org,
        actor_identity_id=actor_id,
        intent_id=intent.id,
        status="EVALUATED",
        outcome="APPROVED",
    )
    db.add(evaluation)
    db.flush()

    decision = Decision(
        organization_id=org,
        governance_evaluation_id=evaluation.id,
        intent_id=intent.id,
        evaluation_id=evaluation.id,
        outcome=DecisionOutcome.APPROVED.value,
        reason_codes='["APPROVED_BY_POLICY"]',
        policy_version="v1",
        decision_hash=f"dh-{suffix}",
        supersession_status=DecisionSupersessionStatus.CURRENT.value,
    )
    db.add(decision)
    db.flush()

    authorization = ExecutionAuthorization(
        organization_id=org,
        decision_id=decision.id,
        intent_id=intent.id,
        status=AuthorizationStatus.ACTIVE.value,
        authorization_token=f"tok-{suffix}",
    )
    db.add(authorization)
    db.commit()
    db.refresh(decision)
    db.refresh(authorization)

    proof = generator.generate_signed_aiproof(
        metadata={
            "aiproof_id": f"aiproof-{uuid.uuid4()}",
            "organization_id": org,
            "governance_evaluation_id": evaluation.id,
            "governed_outcome": "APPROVED_AND_EXECUTED",
        },
        actor_identity={"actor_identity_id": actor_id},
        intent={"intent_id": intent.id},
        decision={
            "decision_id": decision.id,
            "outcome": decision.outcome,
            "decision_hash": decision.decision_hash,
        },
        timestamps={"generated_at": "2026-01-01T00:00:00+00:00"},
    )
    proof_row = aiproof_service.store_aiproof(db, proof)

    return SimpleNamespace(
        org=org,
        actor_id=actor_id,
        intent_id=intent.id,
        evaluation_id=evaluation.id,
        decision_id=decision.id,
        authorization_id=authorization.id,
        aiproof_id=proof_row.id,
    )


# --------------------------------------------------------------------------- #
# ChangeDetector interface
# --------------------------------------------------------------------------- #
def test_state_hash_detector_fires_only_on_change():
    detector = StateHashChangeDetector(MonitoringChangeType.POLICY_CHANGED)
    assert isinstance(get_detector(MonitoringChangeType.POLICY_CHANGED),
                      StateHashChangeDetector)

    unchanged = detector.detect(
        affected_object_type="Policy",
        affected_object_id="pol-1",
        old_state={"threshold": 100},
        new_state={"threshold": 100},
        source="policy-engine",
    )
    assert unchanged == []

    changed = detector.detect(
        affected_object_type="Policy",
        affected_object_id="pol-1",
        old_state={"threshold": 100},
        new_state={"threshold": 10},
        source="policy-engine",
    )
    assert len(changed) == 1
    change = changed[0]
    assert change.change_type == MonitoringChangeType.POLICY_CHANGED
    assert change.old_state_hash == compute_state_hash({"threshold": 100})
    assert change.new_state_hash == compute_state_hash({"threshold": 10})


# --------------------------------------------------------------------------- #
# Monitoring event submission
# --------------------------------------------------------------------------- #
def test_submit_monitoring_event_is_idempotent(db_session):
    event1 = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.POLICY_CHANGED,
        source="policy-engine",
        affected_object_type="Policy",
        affected_object_id="pol-1",
        old_state_hash="a",
        new_state_hash="b",
    )
    event2 = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.POLICY_CHANGED,
        source="policy-engine",
        affected_object_type="Policy",
        affected_object_id="pol-1",
        old_state_hash="a",
        new_state_hash="b",
    )
    assert event1.id == event2.id
    assert event1.event_uid == event2.event_uid


# --------------------------------------------------------------------------- #
# Acceptance: changes trigger impact analysis
# --------------------------------------------------------------------------- #
def test_change_triggers_impact_analysis(db_session):
    seed = _seed_governed_intent(db_session)
    event = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.POLICY_CHANGED,
        source="policy-engine",
        affected_object_type="Policy",
        affected_object_id="pol-x",
        intent_id=seed.intent_id,
        evaluation_id=seed.evaluation_id,
    )
    from app.services.canonical.monitoring import impact_analysis

    impact = impact_analysis.analyze(db_session, ORG, event)
    assert seed.intent_id in impact.intents
    assert seed.evaluation_id in impact.evaluations
    assert seed.decision_id in impact.decisions
    assert seed.authorization_id in impact.authorizations
    assert seed.aiproof_id in impact.aiproofs
    assert not impact.is_empty()


# --------------------------------------------------------------------------- #
# Scenario 1: policy threshold changes before execution
# --------------------------------------------------------------------------- #
def test_scenario_policy_threshold_change(db_session):
    seed = _seed_governed_intent(db_session)
    event = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.POLICY_CHANGED,
        source="policy-engine",
        affected_object_type="Policy",
        affected_object_id="pol-threshold",
        intent_id=seed.intent_id,
        evaluation_id=seed.evaluation_id,
    )
    run = reevaluation_job.trigger(
        db_session,
        ORG,
        event.id,
        resulting_outcome=DecisionOutcome.DENIED.value,
    )
    assert run.status == ReevaluationStatus.COMPLETED.value
    assert run.resulting_outcome == DecisionOutcome.DENIED.value

    # New immutable decision supersedes the prior one; prior remains available.
    new_decision = DecisionRepository(db_session).get(ORG, run.new_decision_id)
    assert new_decision.id != seed.decision_id
    assert new_decision.outcome == DecisionOutcome.DENIED.value
    prior = DecisionRepository(db_session).get(ORG, seed.decision_id)
    assert prior is not None
    assert prior.supersession_status == DecisionSupersessionStatus.SUPERSEDED.value
    assert prior.superseded_by_decision_id == new_decision.id

    # Authorization invalidated (revoked).
    auth = ExecutionAuthorizationRepository(db_session).get(
        ORG, seed.authorization_id
    )
    assert auth.status == AuthorizationStatus.REVOKED.value
    assert seed.authorization_id in run_invalidated(run)

    # Prior proof superseded by a new proof.
    assert run.new_aiproof_id is not None
    assert run.prior_aiproof_id == seed.aiproof_id


def run_invalidated(run):
    import json

    return json.loads(run.invalidated_authorization_ids or "[]")


# --------------------------------------------------------------------------- #
# Scenario 2: evidence expires before authorization is consumed
# --------------------------------------------------------------------------- #
def test_scenario_evidence_expired(db_session):
    seed = _seed_governed_intent(db_session)
    event = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.EVIDENCE_EXPIRED,
        source="evidence-connector",
        affected_object_type="NormalizedEvidence",
        affected_object_id="ev-1",
        intent_id=seed.intent_id,
        evaluation_id=seed.evaluation_id,
    )
    run = reevaluation_job.trigger(db_session, ORG, event.id)
    assert run.status == ReevaluationStatus.COMPLETED.value
    # EVIDENCE_EXPIRED defaults to DENIED.
    assert run.resulting_outcome == DecisionOutcome.DENIED.value
    auth = ExecutionAuthorizationRepository(db_session).get(
        ORG, seed.authorization_id
    )
    # Expiry-driven invalidation transitions to EXPIRED (not REVOKED).
    assert auth.status == AuthorizationStatus.EXPIRED.value
    assert seed.authorization_id in run_invalidated(run)


# --------------------------------------------------------------------------- #
# Scenario 3: agent authority is revoked
# --------------------------------------------------------------------------- #
def test_scenario_actor_authority_revoked(db_session):
    seed = _seed_governed_intent(db_session)
    event = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.ACTOR_AUTHORITY_CHANGED,
        source="identity-registry",
        affected_object_type="ActorIdentity",
        affected_object_id=seed.actor_id,
        intent_id=seed.intent_id,
        evaluation_id=seed.evaluation_id,
    )
    run = reevaluation_job.trigger(db_session, ORG, event.id)
    assert run.status == ReevaluationStatus.COMPLETED.value
    assert run.resulting_outcome == DecisionOutcome.DENIED.value
    auth = ExecutionAuthorizationRepository(db_session).get(
        ORG, seed.authorization_id
    )
    assert auth.status == AuthorizationStatus.REVOKED.value


# --------------------------------------------------------------------------- #
# Scenario 4: finding resolved with valid evidence
# --------------------------------------------------------------------------- #
def test_scenario_finding_resolved(db_session):
    seed = _seed_governed_intent(db_session)
    event = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.FINDING_STATUS_CHANGED,
        source="remediation-branch",
        affected_object_type="Finding",
        affected_object_id="find-1",
        intent_id=seed.intent_id,
        evaluation_id=seed.evaluation_id,
    )
    run = reevaluation_job.trigger(db_session, ORG, event.id)
    assert run.status == ReevaluationStatus.COMPLETED.value
    # A resolved finding restores an APPROVED outcome.
    assert run.resulting_outcome == DecisionOutcome.APPROVED.value
    # Approved re-evaluation for a restorative change leaves authorization live.
    auth = ExecutionAuthorizationRepository(db_session).get(
        ORG, seed.authorization_id
    )
    assert auth.status == AuthorizationStatus.ACTIVE.value
    assert run_invalidated(run) == []
    # A new proof was produced, superseding the prior one.
    new_proof = CanonicalAIProofRepository(db_session).get(
        ORG, run.new_aiproof_id
    )
    assert new_proof.governed_outcome == "REMEDIATED_AND_REEVALUATED"


# --------------------------------------------------------------------------- #
# Scenario 5: external execution result changes pending -> completed
# --------------------------------------------------------------------------- #
def test_scenario_external_result_changed(db_session):
    seed = _seed_governed_intent(db_session)
    event = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.EXTERNAL_EXECUTION_RESULT_CHANGED,
        source="execution-adapter",
        affected_object_type="ExternalExecutionResult",
        affected_object_id="xr-1",
        intent_id=seed.intent_id,
        evaluation_id=seed.evaluation_id,
    )
    run = reevaluation_job.trigger(db_session, ORG, event.id)
    assert run.status == ReevaluationStatus.COMPLETED.value
    # No default disposition -> the prior APPROVED outcome is preserved.
    assert run.resulting_outcome == DecisionOutcome.APPROVED.value
    auth = ExecutionAuthorizationRepository(db_session).get(
        ORG, seed.authorization_id
    )
    assert auth.status == AuthorizationStatus.ACTIVE.value


# --------------------------------------------------------------------------- #
# Scenario 6: proof is superseded after re-evaluation (visible + verifiable)
# --------------------------------------------------------------------------- #
def test_scenario_proof_superseded_visible_and_verifiable(db_session):
    seed = _seed_governed_intent(db_session)
    event = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.POLICY_CHANGED,
        source="policy-engine",
        affected_object_type="Policy",
        affected_object_id="pol-1",
        intent_id=seed.intent_id,
        evaluation_id=seed.evaluation_id,
    )
    run = reevaluation_job.trigger(
        db_session, ORG, event.id, resulting_outcome=DecisionOutcome.DENIED.value
    )

    # Prior proof retained + marked superseded; chain shows both.
    prior_row = CanonicalAIProofRepository(db_session).get(ORG, seed.aiproof_id)
    assert prior_row.status == "SUPERSEDED"
    assert prior_row.superseded_by_aiproof_id == run.new_aiproof_id

    chain = proof_supersession.proof_chain(db_session, ORG, seed.aiproof_id)
    assert chain["length"] == 2
    assert chain["root_aiproof_id"] == seed.aiproof_id
    assert chain["current_aiproof_id"] == run.new_aiproof_id

    # The new proof independently verifies (schema + signature).
    new_proof = aiproof_service.get_aiproof(db_session, ORG, run.new_aiproof_id)
    result = verify_aiproof(new_proof)
    assert result.valid
    assert new_proof.prior_aiproof_id == seed.aiproof_id


# --------------------------------------------------------------------------- #
# Acceptance: historical decisions remain available via the supersession chain
# --------------------------------------------------------------------------- #
def test_decision_supersession_chain(db_session):
    seed = _seed_governed_intent(db_session)
    event = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.POLICY_CHANGED,
        source="policy-engine",
        affected_object_type="Policy",
        affected_object_id="pol-1",
        intent_id=seed.intent_id,
        evaluation_id=seed.evaluation_id,
    )
    run = reevaluation_job.trigger(
        db_session, ORG, event.id, resulting_outcome=DecisionOutcome.DENIED.value
    )
    chain = supersession_service.decision_chain(db_session, ORG, seed.decision_id)
    assert chain["length"] == 2
    assert chain["root_decision_id"] == seed.decision_id
    assert chain["current_decision_id"] == run.new_decision_id
    outcomes = [entry["outcome"] for entry in chain["chain"]]
    assert outcomes == [DecisionOutcome.APPROVED.value, DecisionOutcome.DENIED.value]


# --------------------------------------------------------------------------- #
# No-op re-evaluation when nothing is affected
# --------------------------------------------------------------------------- #
def test_reevaluation_no_action_when_nothing_affected(db_session):
    event = monitoring_service.submit_event(
        db_session,
        ORG,
        change_type=MonitoringChangeType.POLICY_CHANGED,
        source="policy-engine",
        affected_object_type="Policy",
        affected_object_id="pol-unlinked",
    )
    run = reevaluation_job.trigger(db_session, ORG, event.id)
    assert run.status == ReevaluationStatus.NO_ACTION.value
    assert run.new_decision_id is None


# --------------------------------------------------------------------------- #
# API surface
# --------------------------------------------------------------------------- #
def test_monitoring_api_end_to_end(api_client):
    headers = {"X-Organization-Id": ORG}
    submit = api_client.post(
        "/api/v1/monitoring/events",
        json={
            "organization_id": ORG,
            "change_type": "POLICY_CHANGED",
            "source": "policy-engine",
            "affected_object_type": "Policy",
            "affected_object_id": "pol-api",
        },
    )
    assert submit.status_code == 201, submit.text
    event_id = submit.json()["id"]

    # Impact endpoint responds (empty scope for an unlinked policy change).
    impact = api_client.get(
        f"/api/v1/monitoring/events/{event_id}/impact", headers=headers
    )
    assert impact.status_code == 200
    assert impact.json()["monitoring_event_id"] == event_id

    # Trigger re-evaluation.
    reeval = api_client.post(
        f"/api/v1/monitoring/events/{event_id}/reevaluate",
        headers=headers,
        json={},
    )
    assert reeval.status_code == 201, reeval.text
    run_id = reeval.json()["id"]

    status = api_client.get(
        f"/api/v1/monitoring/reevaluations/{run_id}", headers=headers
    )
    assert status.status_code == 200
    assert status.json()["status"] == ReevaluationStatus.NO_ACTION.value

    listing = api_client.get(
        "/api/v1/monitoring/events", headers=headers
    )
    assert listing.status_code == 200
    assert any(e["id"] == event_id for e in listing.json())


def test_missing_org_is_rejected(api_client):
    resp = api_client.get("/api/v1/monitoring/events")
    assert resp.status_code == 400
