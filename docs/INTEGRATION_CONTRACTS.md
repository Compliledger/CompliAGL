# Integration Contracts: ProofSync, AuditSync, RegSync

This document defines the formal integration contracts and event feeds that
connect the **canonical CompliLedger Proof Infrastructure** (CompliAGL) to the
three downstream sync portals. The portals do **not** own proof state — they
are authorized, projected, real-time views of the single canonical source.

> Canonical source of truth: the CompliAGL/CompliLedger proof and governance
> tables. ProofSync, AuditSync and RegSync never store independent proofs; they
> consume signed, scoped projections of canonical events. There is exactly one
> proof store.

## Channels and responsibilities

| Channel | Audience | Responsibilities |
| --- | --- | --- |
| **ProofSync** | Client / governance owner | Client-facing real-time governance & assurance feed: current assessment status, decision status, proof verification status, finding status, remediation status, change history, continuous-monitoring events. |
| **AuditSync** | Authorized auditor | Auditor-authorized access: evidence *references*, proof verification, assessment history, finding history, remediation history, resolution history, scoped exports. |
| **RegSync** | Authorized regulator | Regulator-authorized access: regulation-specific proof views, applicable requirement mapping, independent verification, continuous supervision, examination history, regulatory reporting. |

Channel responsibilities and authorized roles are declared as data in
`app/services/canonical/integration/contracts.py`
(`CHANNEL_RESPONSIBILITIES`, `CHANNEL_AUTHORIZED_ROLES`).

### Role scoping

| Channel | Authorized subscriber roles |
| --- | --- |
| ProofSync | `CLIENT`, `GOVERNANCE_ADMIN`, `COMPLILEDGER_SERVICE` |
| AuditSync | `AUDITOR`, `COMPLILEDGER_SERVICE` |
| RegSync | `REGULATOR`, `COMPLILEDGER_SERVICE` |

Every request to a channel feed is scoped by **organization** (tenant isolation
is enforced at the repository layer) and by **subscriber role**
(`app/services/canonical/integration/scoping.py`). Unauthorized role/channel
combinations are rejected with a `ScopeError`.

## Event contracts

The following canonical event types are published to the outbox and fanned out
to every channel as a per-channel projection:

- `assessment.created`
- `decision.created`
- `finding.created`
- `remediation.updated`
- `resolution.validated`
- `proof.generated`
- `proof.anchored`
- `proof.verified`
- `proof.superseded`
- `monitoring.change_detected`
- `reevaluation.completed`

Each event carries: a deterministic `event_id`, `event_type`, `aggregate_type`,
`aggregate_id`, `occurred_at`, non-sensitive `references`/`attributes`, a
digest of any sensitive fields, and a `payload_hash`.

## Reliability guarantees

1. **Transactional outbox.** Events are written to `integration_events` with
   their per-channel `event_deliveries` rows in a single transaction
   (`event_publisher.publish`). Emission from canonical services uses
   `emit_safe`, which never raises and rolls back its own outbox write on
   failure so canonical state is never corrupted.
2. **Persisted delivery state.** Every `(event, channel)` pair has a durable
   `EventDelivery` row with `status`, `attempts`, `last_error`,
   `next_retry_at`, and `external_reference`.
3. **Retry and dead-letter.** The dispatcher retries `PENDING`/`FAILED`
   deliveries with linear back-off. When `attempts >= max_attempts` the
   delivery transitions to `DEAD_LETTER`. `retry_delivery` re-opens a
   dead-lettered delivery for one further attempt.
4. **Idempotent consumers.** `event_id` is deterministic (derived from event
   type, org, aggregate identity and a dedup key). Re-publishing the same
   logical event returns the existing outbox row without creating duplicate
   deliveries, and `IdempotentEventConsumer` deduplicates on the consumer side.

## Security guarantees

- **Signed events.** Every delivery projection is signed with HMAC-SHA256
  (`event_signing.py`), using env-configured `EVENT_SIGNING_KEYS` with a
  `SECRET_KEY`-derived development key so events are always signed. Consumers
  verify `signer_key_id` + `signature` against the projection hash.
- **No raw sensitive evidence by default.** Sensitive fields are never stored
  or forwarded in the clear. Projections carry only references and
  `{redacted: true, sha256: ...}` digests (`projections.py`). Auditors and
  regulators receive evidence *references*, not raw evidence bytes.
- **Authorized projections.** Each channel receives a distinct projection
  (`assurance_view` / `audit_view` / `regulatory_view`) with an explicit
  `redacted_fields` list.

## API surface

Read/operational endpoints live under `/api/v1/integration`:

- `GET /integration/contracts` — formal channel/role/event contract manifest.
- `GET /integration/events` — canonical outbox events (org-scoped).
- `GET /integration/events/{event_id}/deliveries` — per-channel delivery state.
- `GET /integration/{channel}/feed` — signed, projected feed for a channel
  (org + role scoped).
- `GET /integration/{channel}/deliveries` — delivery state for a channel.
- `POST /integration/dispatch` — dispatch pending deliveries.
- `POST /integration/deliveries/{delivery_id}/retry` — retry / re-open a
  dead-lettered delivery.

Organization scope is supplied via `X-Organization-Id`; subscriber role via
`X-Subscriber-Role`.

## Adapters

`IntegrationChannelAdapter` (`channel_adapter.py`) is the interface each portal
implements. The real ProofSync/AuditSync/RegSync portal code lives in separate
repositories; this repo ships in-memory reference adapters and a registry
(`register_adapter` / `get_adapter`) so the canonical side is fully testable
and portal implementations can be swapped in without touching canonical code.
