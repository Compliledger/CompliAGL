# HarborStone sanctions-screening: evidence contract + connector

**Status:** active as of HarborStone package **v1.2.1**. Supersedes
`PENDING_REVIEW_harborstone_screening_control_placeholder.md` (removed) and the
`*-PLACEHOLDER-SANCTIONS-SCREENING` requirement/control pair + env-gated
placeholder connector it described.

## What is real vs simulated

The connector `app/services/evidence/connectors/harborstone_sentry_screening.py`
is a **real evidence connector**. It is registered by default in
`default_production_registry()` (no env-gate), it runs on the production
collection path under the Gateway's `production_mode=True` (`is_mock=False`),
and it returns a structured, integrity-hashed evidence item. Everything
downstream of that item — validation, normalization, control evaluation
(`CTL-HARBORSTONE-SANCTIONS-SCREENING`), the decision engine, enforcement, and
the CompliLedger / CompliAegis flow around it — is real.

The screening subject is the **counterparty** — the evidence requirement binds
its subject to the Target's `external_identifier` (`subject_binding: "target"`),
so a driver controls the screening outcome by setting the counterparty account
it submits.

**Simulated:** only the screening *lookup itself*. Instead of calling OFAC or a
sanctions-list vendor, the connector resolves the screening subject against a
fixed in-repo dataset (`_DEMO_SANCTIONS_DATASET`):

| subject | result | risk | `requires_human_review` |
|---|---|---|---|
| `wallet_001` (`0xW001`) | `NO_MATCH` | LOW | false |
| `wallet_002` (`0xW002`) | `POTENTIAL_MATCH` | HIGH | true |
| `wallet_003` (`0xW003`) | `CONFIRMED_MATCH` | CRITICAL | true |
| `0.0.3` | `NO_MATCH` | LOW | false |
| *anything else* | `NO_MATCH` | LOW | false *(documented default)* |

This is a deliberate, project-owner-approved (Maranda) MVP choice. The connector
is honest about it: every item carries `claims.simulation = true`, a
`claims.simulation_note`, `screening_source = "DEMO_SANCTIONS_SOURCE"`, and each
`collect()` call logs it. Replacing the dataset lookup with a real vendor call
is a change confined to `_lookup()` — nothing else moves.

## Evidence contract (`claims`) — `demo3.sanctions-screening.v1`

```json
{
  "schema_version": "demo3.sanctions-screening.v1",
  "screening_id": "scr_...",              // sha256(subject | requirement_id)[:16]
  "tenant_id": "harborstone-demo",         // connector is tenant-scoped
  "case_id": "...",                        // the resource instance screened
  "correlation_id": "corr_...",            // from the intent id, when present
  "delegation_id": null,                   // not observable from a CollectRequest
  "requesting_agent_id": "agent:harborstone:aira",
  "screening_agent_id": "agent:harborstone:sentry",
  "subject": {"type": "wallet", "id": "..."},
  "scope": "SANCTIONS_SCREENING_ONLY",
  "screening_source": "DEMO_SANCTIONS_SOURCE",
  "screened_at": "UTC ISO-8601",
  "result": "NO_MATCH | POTENTIAL_MATCH | CONFIRMED_MATCH | NOT_EVALUABLE",
  "match_count": 0,
  "risk_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "requires_human_review": false,
  "evidence_refs": ["evidence_ref_..."],
  "authority_context_ref": null,           // not observable from a CollectRequest
  "delegation_context_ref": null,          // not observable from a CollectRequest
  "simulation": true,
  "simulation_note": "...",
  "integrity_hash": "..."                  // sha256 over the canonical claims
}
```

`delegation_id` / `authority_context_ref` / `delegation_context_ref` are `null`
on purpose — a `CollectRequest` does not carry them and the connector never
fabricates integrity metadata it did not observe (same discipline as
`securerob.py`). The authority/delegation context for the run is bound
elsewhere: on the CompliAGL `Decision` (`authority_hash`) and on the
CompliIdentity delegation the Gateway used.

## Routing (HarborStone package v1.2.1)

- `CTL-HARBORSTONE-SANCTIONS-SCREENING` (mandatory) is SATISFIED only on
  `result == "NO_MATCH"`.
- `DC-HARBORSTONE-SANCTIONS-CONFIRMED` (priority 11) → `CONFIRMED_MATCH` is a
  terminal `DENIED`.
- `DC-HARBORSTONE-SANCTIONS-REVIEW` (priority 12) → any result flagged
  `requires_human_review` (`POTENTIAL_MATCH`) → `ESCALATED`
  (`_resolve_outcome` maps `NOT_SATISFIED` assessment + `ESCALATED` condition to
  `ESCALATED`, not a hard deny).
- `NO_MATCH` → assessment SATISFIED → the normal amount/authority path
  (`APPROVED` sub-threshold, `ESCALATED` at / above the $250K threshold).

Both screening conditions read `evidence_claims['EV-HARBORSTONE-SANCTIONS-SCREENING']`
— the normalized screening claims, surfaced into the decision context by
`decision_service._evidence_claims_facts` (a generic mechanism; it mirrors the
evidence-fact vocabulary `control_evaluation_service` already exposes to
control expressions).

## Tests

- `backend/tests/test_harborstone_sentry_screening_connector.py`
- `backend/tests/test_harborstone_package.py` (control expression + condition
  ordering)
- `backend/tests/test_decision_evidence_claims.py` (`evidence_claims` surfacing)
- `backend/tests/test_harborstone_screening_pipeline.py` (end-to-end:
  NO_MATCH → APPROVED, CONFIRMED_MATCH → DENIED, POTENTIAL_MATCH → ESCALATED)
