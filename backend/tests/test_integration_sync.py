"""Tests for the ProofSync / AuditSync / RegSync integration contracts.

Covers the acceptance scenarios:

* tenant isolation,
* auditor scope,
* regulator scope,
* failed event delivery (retry + dead-letter),
* duplicate event handling (idempotency),
* proof supersession propagation,
* sensitive evidence redaction.
"""

from __future__ import annotations

import json

import pytest

from app.repositories.canonical import (
    EventDeliveryRepository,
    IntegrationEventRepository,
)
from app.services.canonical.integration import (
    dispatcher,
    event_publisher,
    event_signing,
    scoping,
)
from app.services.canonical.integration import channel_adapter
from app.services.canonical.integration.channel_adapter import (
    ChannelDeliveryResult,
    IntegrationChannelAdapter,
)
from app.services.canonical.integration.consumer import IdempotentEventConsumer
from app.services.canonical.integration.contracts import (
    ALL_CHANNELS,
    EventContract,
)
from app.services.canonical.integration.projections import build_projection
from app.utils.canonical_enums import (
    EventDeliveryStatus,
    IntegrationChannel,
    IntegrationEventType,
    SubscriberRole,
)

ORG_A = "org-alpha"
ORG_B = "org-beta"

RAW_SECRET = {"passport_number": "X1234567", "dob": "1990-01-01"}


@pytest.fixture(autouse=True)
def _reset_adapters():
    """Ensure a clean adapter registry around every test."""
    channel_adapter.reset_adapters()
    yield
    channel_adapter.reset_adapters()


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def _assessment_event(org=ORG_A, aggregate_id="assess-1", **kw) -> EventContract:
    return EventContract(
        event_type=IntegrationEventType.ASSESSMENT_CREATED,
        organization_id=org,
        aggregate_type="Assessment",
        aggregate_id=aggregate_id,
        references={
            "assessment_id": aggregate_id,
            "requirement_ids": ["REQ-1", "REQ-2"],
            "evidence_references": ["ev-1", "ev-2"],
            "proof_hash": "ph-abc",
        },
        attributes={"status": "SATISFIED", "outcome": "SATISFIED"},
        **kw,
    )


class _FailingAdapter(IntegrationChannelAdapter):
    def __init__(self, channel: IntegrationChannel):
        self.channel = channel
        self.name = f"failing:{channel.value.lower()}"

    def deliver(self, delivery) -> ChannelDeliveryResult:
        return ChannelDeliveryResult(accepted=False, detail="portal unavailable")


# --------------------------------------------------------------------------- #
# Publishing: outbox + fan-out + signing
# --------------------------------------------------------------------------- #
def test_publish_creates_outbox_event_and_channel_deliveries(db_session):
    event = event_publisher.publish(db_session, _assessment_event())

    stored = IntegrationEventRepository(db_session).get_by_event_id(
        ORG_A, event.event_id
    )
    assert stored is not None
    deliveries = EventDeliveryRepository(db_session).list_for_event(
        ORG_A, event.event_id
    )
    assert {d.channel for d in deliveries} == {c.value for c in ALL_CHANNELS}
    # Each delivery starts PENDING and is signed over its projection hash.
    for d in deliveries:
        assert d.status == EventDeliveryStatus.PENDING.value
        assert d.signature and d.signer_key_id
        assert event_signing.verify(
            d.signer_key_id, d.projection_hash, d.signature
        )


def test_publish_persists_only_digests_never_raw_sensitive(db_session):
    event = event_publisher.publish(
        db_session, _assessment_event(sensitive={"raw_evidence": RAW_SECRET})
    )
    stored = IntegrationEventRepository(db_session).get_by_event_id(
        ORG_A, event.event_id
    )
    blob = stored.references + stored.attributes + stored.sensitive_digest
    assert "X1234567" not in blob
    digest = json.loads(stored.sensitive_digest)
    assert digest["raw_evidence"]["redacted"] is True
    assert digest["raw_evidence"]["sha256"]


# --------------------------------------------------------------------------- #
# Sensitive evidence redaction (all channels)
# --------------------------------------------------------------------------- #
def test_projection_never_leaks_raw_sensitive_evidence():
    contract = _assessment_event(sensitive={"raw_evidence": RAW_SECRET})
    for channel in ALL_CHANNELS:
        projection = build_projection(contract, channel)
        serialized = json.dumps(projection)
        assert "X1234567" not in serialized
        assert "1990-01-01" not in serialized
        # The sensitive field is present only as a redaction marker + digest.
        assert projection["redacted_fields"]["raw_evidence"]["redacted"] is True
        assert projection["redacted_fields"]["raw_evidence"]["sha256"]
        # Safe references ARE projected.
        assert projection["references"]["evidence_references"] == ["ev-1", "ev-2"]


def test_delivered_projection_has_no_raw_sensitive(db_session):
    event = event_publisher.publish(
        db_session, _assessment_event(sensitive={"raw_evidence": RAW_SECRET})
    )
    for d in EventDeliveryRepository(db_session).list_for_event(
        ORG_A, event.event_id
    ):
        assert "X1234567" not in d.projection


# --------------------------------------------------------------------------- #
# Idempotency / duplicate handling
# --------------------------------------------------------------------------- #
def test_duplicate_publish_is_idempotent(db_session):
    first = event_publisher.publish(db_session, _assessment_event())
    second = event_publisher.publish(db_session, _assessment_event())
    assert first.id == second.id
    # No duplicate outbox rows and no duplicate deliveries.
    assert IntegrationEventRepository(db_session).count(ORG_A) == 1
    deliveries = EventDeliveryRepository(db_session).list_for_event(
        ORG_A, first.event_id
    )
    assert len(deliveries) == len(ALL_CHANNELS)


def test_dedup_key_distinguishes_distinct_events(db_session):
    a = event_publisher.publish(db_session, _assessment_event(dedup_key="v1"))
    b = event_publisher.publish(db_session, _assessment_event(dedup_key="v2"))
    assert a.event_id != b.event_id
    assert IntegrationEventRepository(db_session).count(ORG_A) == 2


def test_idempotent_consumer_processes_once():
    consumer = IdempotentEventConsumer()
    contract = _assessment_event()
    delivered = build_projection(contract, IntegrationChannel.PROOFSYNC)
    seen: list[str] = []
    handler = lambda p: seen.append(p["event_id"])  # noqa: E731

    assert consumer.process(delivered, handler) is True
    # A re-delivery of the same event is skipped (at-least-once -> exactly-once).
    assert consumer.process(delivered, handler) is False
    assert len(seen) == 1


# --------------------------------------------------------------------------- #
# Tenant isolation
# --------------------------------------------------------------------------- #
def test_events_are_tenant_isolated(db_session):
    event_publisher.publish(db_session, _assessment_event(org=ORG_A))
    event_publisher.publish(
        db_session, _assessment_event(org=ORG_B, aggregate_id="assess-b")
    )
    repo = IntegrationEventRepository(db_session)
    assert repo.count(ORG_A) == 1
    assert repo.count(ORG_B) == 1
    a_events = repo.list(ORG_A)
    assert all(e.organization_id == ORG_A for e in a_events)


def test_deliveries_are_tenant_isolated(db_session):
    a = event_publisher.publish(db_session, _assessment_event(org=ORG_A))
    # ORG_B cannot see ORG_A's deliveries.
    assert (
        EventDeliveryRepository(db_session).list_for_event(ORG_B, a.event_id)
        == []
    )


# --------------------------------------------------------------------------- #
# Role scoping (auditor / regulator / client)
# --------------------------------------------------------------------------- #
def test_channel_role_scoping_matrix():
    assert scoping.is_authorized(
        IntegrationChannel.AUDITSYNC, SubscriberRole.AUDITOR
    )
    assert scoping.is_authorized(
        IntegrationChannel.REGSYNC, SubscriberRole.REGULATOR
    )
    assert scoping.is_authorized(
        IntegrationChannel.PROOFSYNC, SubscriberRole.CLIENT
    )
    # Cross-role access is denied.
    assert not scoping.is_authorized(
        IntegrationChannel.AUDITSYNC, SubscriberRole.CLIENT
    )
    assert not scoping.is_authorized(
        IntegrationChannel.REGSYNC, SubscriberRole.AUDITOR
    )
    assert not scoping.is_authorized(
        IntegrationChannel.PROOFSYNC, SubscriberRole.REGULATOR
    )


def test_authorize_raises_for_unauthorized_role():
    with pytest.raises(scoping.ScopeError):
        scoping.authorize(IntegrationChannel.REGSYNC, SubscriberRole.CLIENT)


# --------------------------------------------------------------------------- #
# Reliable delivery: success, retry, dead-letter
# --------------------------------------------------------------------------- #
def test_dispatch_delivers_pending(db_session):
    event = event_publisher.publish(db_session, _assessment_event())
    summary = dispatcher.dispatch_pending(db_session, ORG_A)
    assert summary.delivered == len(ALL_CHANNELS)
    for d in EventDeliveryRepository(db_session).list_for_event(
        ORG_A, event.event_id
    ):
        assert d.status == EventDeliveryStatus.DELIVERED.value
        assert d.delivered_at is not None
        assert d.external_reference


def test_failed_delivery_is_retryable_then_recovers(db_session):
    channel_adapter.register_adapter(_FailingAdapter(IntegrationChannel.REGSYNC))
    event = event_publisher.publish(db_session, _assessment_event())
    repo = EventDeliveryRepository(db_session)

    dispatcher.dispatch_pending(db_session, ORG_A)
    regsync = next(
        d
        for d in repo.list_for_event(ORG_A, event.event_id)
        if d.channel == IntegrationChannel.REGSYNC.value
    )
    assert regsync.status == EventDeliveryStatus.FAILED.value
    assert regsync.attempts == 1
    assert regsync.last_error
    assert regsync.next_retry_at is not None

    # Portal recovers -> a manual retry delivers successfully.
    channel_adapter.reset_adapters()
    recovered = dispatcher.retry_delivery(db_session, ORG_A, regsync.id)
    assert recovered.status == EventDeliveryStatus.DELIVERED.value


def test_delivery_is_dead_lettered_after_max_attempts(db_session):
    channel_adapter.register_adapter(
        _FailingAdapter(IntegrationChannel.AUDITSYNC)
    )
    event = event_publisher.publish(db_session, _assessment_event())
    repo = EventDeliveryRepository(db_session)
    auditsync = next(
        d
        for d in repo.list_for_event(ORG_A, event.event_id)
        if d.channel == IntegrationChannel.AUDITSYNC.value
    )
    auditsync.max_attempts = 2
    repo.save(auditsync)

    # First failure -> FAILED (retryable).
    dispatcher.dispatch_delivery(db_session, auditsync)
    assert auditsync.status == EventDeliveryStatus.FAILED.value
    # Second failure exhausts the budget -> DEAD_LETTER.
    dispatcher.dispatch_delivery(db_session, auditsync)
    assert auditsync.status == EventDeliveryStatus.DEAD_LETTER.value
    # Dead-lettered deliveries are not returned as deliverable.
    assert auditsync.id not in {
        d.id for d in repo.list_deliverable(ORG_A)
    }


# --------------------------------------------------------------------------- #
# Proof supersession propagation
# --------------------------------------------------------------------------- #
def test_proof_supersession_propagates_to_all_channels(db_session):
    superseded = EventContract(
        event_type=IntegrationEventType.PROOF_SUPERSEDED,
        organization_id=ORG_A,
        aggregate_type="Decision",
        aggregate_id="dec-old",
        references={
            "decision_id": "dec-old",
            "superseded_by_decision_id": "dec-new",
            "proof_hash": "ph-old",
        },
        attributes={"status": "SUPERSEDED", "outcome": "APPROVED"},
    )
    event = event_publisher.publish(db_session, superseded)
    dispatcher.dispatch_pending(db_session, ORG_A)

    deliveries = EventDeliveryRepository(db_session).list_for_event(
        ORG_A, event.event_id
    )
    assert {d.channel for d in deliveries} == {c.value for c in ALL_CHANNELS}
    for d in deliveries:
        assert d.status == EventDeliveryStatus.DELIVERED.value
        projection = json.loads(d.projection)
        assert projection["event_type"] == "proof.superseded"
        assert (
            projection["references"]["superseded_by_decision_id"] == "dec-new"
        )


# --------------------------------------------------------------------------- #
# API-level scoping + feeds
# --------------------------------------------------------------------------- #
def test_contracts_endpoint_lists_channels_and_events(api_client):
    resp = api_client.get("/api/v1/integration/contracts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["canonical_source"] == "compliledger"
    assert "assessment.created" in body["event_types"]
    assert "proof.superseded" in body["event_types"]
    channels = {c["channel"]: c for c in body["channels"]}
    assert set(channels) == {"PROOFSYNC", "AUDITSYNC", "REGSYNC"}
    assert "AUDITOR" in channels["AUDITSYNC"]["authorized_roles"]
    assert "REGULATOR" in channels["REGSYNC"]["authorized_roles"]


def test_feed_requires_tenant_and_role(api_client):
    # Missing tenant.
    r1 = api_client.get(
        "/api/v1/integration/AUDITSYNC/feed",
        headers={"X-Subscriber-Role": "AUDITOR"},
    )
    assert r1.status_code == 400
    # Missing role.
    r2 = api_client.get(
        "/api/v1/integration/AUDITSYNC/feed",
        headers={"X-Organization-Id": ORG_A},
    )
    assert r2.status_code == 400


def test_feed_rejects_unauthorized_role(api_client):
    resp = api_client.get(
        "/api/v1/integration/REGSYNC/feed",
        headers={"X-Organization-Id": ORG_A, "X-Subscriber-Role": "AUDITOR"},
    )
    assert resp.status_code == 403


def test_feed_returns_scoped_projections_via_api(api_client):
    # Drive a real publish through the app's DB session by invoking the wired
    # finding.created hook: generate findings requires a full pipeline, so we
    # instead publish directly against the same session used by the app.
    from app.core.database import get_db
    from app.main import app

    db = next(app.dependency_overrides[get_db]())
    try:
        event_publisher.publish(db, _assessment_event(org=ORG_A))
    finally:
        db.close()

    # Auditor may read AuditSync.
    ok = api_client.get(
        "/api/v1/integration/AUDITSYNC/feed",
        headers={"X-Organization-Id": ORG_A, "X-Subscriber-Role": "AUDITOR"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["channel"] == "AUDITSYNC"
    assert body["count"] == 1
    projection = body["items"][0]["projection"]
    assert "audit_view" in projection
    assert "X1234567" not in json.dumps(projection)

    # Cross-tenant read returns an empty feed (tenant isolation).
    empty = api_client.get(
        "/api/v1/integration/AUDITSYNC/feed",
        headers={"X-Organization-Id": ORG_B, "X-Subscriber-Role": "AUDITOR"},
    )
    assert empty.status_code == 200
    assert empty.json()["count"] == 0


def test_dispatch_and_retry_endpoints(api_client):
    from app.core.database import get_db
    from app.main import app

    db = next(app.dependency_overrides[get_db]())
    try:
        event = event_publisher.publish(db, _assessment_event(org=ORG_A))
        event_id = event.event_id
    finally:
        db.close()

    resp = api_client.post(
        "/api/v1/integration/dispatch",
        headers={"X-Organization-Id": ORG_A},
    )
    assert resp.status_code == 200
    assert resp.json()["delivered"] == len(ALL_CHANNELS)

    deliveries = api_client.get(
        f"/api/v1/integration/events/{event_id}/deliveries",
        headers={"X-Organization-Id": ORG_A},
    )
    assert deliveries.status_code == 200
    assert all(
        d["status"] == "DELIVERED" for d in deliveries.json()
    )


# --------------------------------------------------------------------------- #
# End-to-end: wired governance hooks emit integration events
# --------------------------------------------------------------------------- #
def test_governance_flow_emits_finding_and_supersession_events(db_session):
    """The real remediation flow publishes finding.created, proof.superseded
    and reevaluation.completed events through the outbox."""
    from tests.test_remediation import (
        ORG as REM_ORG,
        _escalated_control_failure,
    )
    from app.services.canonical import (
        finding_service,
        reassessment_service,
    )

    _, _, _, decision = _escalated_control_failure(db_session)
    finding = finding_service.generate_for_decision(
        db_session, REM_ORG, decision.id
    )[0]

    # finding.created was published to the outbox and fanned out to all portals.
    repo = IntegrationEventRepository(db_session)
    finding_events = [
        e for e in repo.list(REM_ORG) if e.event_type == "finding.created"
    ]
    assert finding_events, "expected a finding.created event"
    fdeliveries = EventDeliveryRepository(db_session).list_for_event(
        REM_ORG, finding_events[0].event_id
    )
    assert {d.channel for d in fdeliveries} == {c.value for c in ALL_CHANNELS}

    # Mark the finding's resolution validated (the validation path itself is
    # covered in test_remediation) and re-assess: the supersession of the prior
    # decision/proof must propagate to the portals.
    from app.repositories.canonical import FindingRepository
    from app.utils.canonical_enums import (
        FindingStatus,
        ResolutionValidationOutcome,
    )

    finding.resolution_validation_outcome = (
        ResolutionValidationOutcome.VALIDATED.value
    )
    finding.status = FindingStatus.RESOLVED_PENDING_VALIDATION.value
    FindingRepository(db_session).save(finding)

    reassessed = reassessment_service.trigger(db_session, REM_ORG, finding.id)
    assert reassessed["reassessed"] is True

    types = {e.event_type for e in repo.list(REM_ORG)}
    assert "proof.superseded" in types
    assert "reevaluation.completed" in types

