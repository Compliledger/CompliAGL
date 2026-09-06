# Pending Review: HarborStone package uses a placeholder sanctions-screening control

**Date:** 2026-09-05
**Status:** Open. Must be replaced before any real HarborStone demo run.
**Introduced by:** authoring `app/db/harborstone_package.py` /
`tests/test_harborstone_governance_package.py` per
`HARBORSTONE_GOVERNANCE_PACKAGE_DESIGN.md`.

---

## What this is

`HARBORSTONE_GOVERNANCE_PACKAGE_DESIGN.md` covers only the HarborStone
package's **decision conditions** (authority-context handling, the $250K
amount threshold). It explicitly states it does *not* cover "the Assessment
stage (what makes AML/sanctions screening SATISFIED vs NOT_SATISFIED in the
first place — presumably SENTRY's screening result feeds this)."

A governance package cannot validate or run without at least one
`requirement` and one mandatory `control_definition` mapped to it (enforced
by `package_json_schema.py`'s structural + traceability checks), and the
decision conditions all key off `assessment == SATISFIED`. Since no real
screening-control design exists yet, `app/db/harborstone_package.py` ships a
**placeholder** requirement/control pair, named unambiguously so it cannot
be mistaken for real content:

- `REQ-PLACEHOLDER-SANCTIONS-SCREENING`
- `CTL-PLACEHOLDER-SANCTIONS-SCREENING`

Its `evaluation_expression` is trivially `"True"` — it does not evaluate any
real screening signal. It exists only so the package is structurally valid
and so the decision-engine wiring (authority-context handling, amount
threshold, fail-closed behavior) can be exercised end-to-end in tests.

## Placeholder evidence connector (HTTP path)

The in-process driver `demo3_step2/compliagl_scenarios.py` satisfies the
placeholder evidence requirement `EV-PLACEHOLDER-SANCTIONS-SCREENING` by
injecting a mock connector (`sim-harborstone-screening-PLACEHOLDER`,
`is_mock=True`) directly into `start_collection`. That injection point is not
reachable over HTTP: `POST /evidence-collections` always uses
`default_production_registry()`, which had no connector for the evidence type
`harborstone.sanctions_screening_placeholder`, so over HTTP the mandatory
control fails closed (`MANDATORY_CONTROL_FAILED`) and the decision-engine +
CompliIdentity authority chain could not be exercised end to end.

`app/services/evidence/connectors/harborstone_screening_placeholder.py` is the
HTTP-path analog. It screens nothing — it returns the same hardcoded
`STANDIN_PASS` claim, issuer (`harborstone-screening-placeholder.example`) and
stand-in signature string as the in-process mock.

Guardrails, because it must never be mistaken for real screening:

- **Not registered by default.** `default_production_registry()` adds it only
  when `COMPLIAGL_HARBORSTONE_SCREENING_PLACEHOLDER` is set to the exact string
  `stand-in-not-real-screening` (an explicit acknowledgement, not a truthy
  flag). Unset — the normal state, and the only state for any real deployment —
  the evidence type has no connector and the mandatory control fails closed,
  exactly as before.
- Every `collect()` call logs a `WARNING`.
- `connector_id`, issuer, `claims.placeholder`, `claims.screening_result` and
  the signature string all say "placeholder" in plain text.
- `is_mock=False` **on purpose**: the Gateway sends `production_mode=True`, and
  the orchestrator rejects `is_mock` connectors in production mode
  (`REJECTED_MOCK`), so a mock here would never run on the path this exists to
  exercise. The env-gate is the guardrail, not `is_mock`.

Retire this connector **and** its `production.py` env-gate together with the
placeholder requirement/control below.

## What replaces it

Real AML/sanctions-screening requirement + control content, reflecting
whatever SENTRY's actual screening output looks like (result field name,
pass/fail semantics, evidence source/connector) — not yet designed anywhere
as of this writing. Whoever designs that is also the one who should retire
this placeholder (requirement, control, **and** the placeholder evidence
connector + its env-gate).

## What must NOT happen

This placeholder must not be used in any real HarborStone demo run, and the
tests built against it
(`tests/test_harborstone_governance_package.py`,
`tests/test_harborstone_screening_placeholder_connector.py`) must not be read
as evidence that sanctions screening works — they test the decision-engine
wiring only (see each file's own module docstring for the same caveat).

`COMPLIAGL_HARBORSTONE_SCREENING_PLACEHOLDER` must not be set in any real
deployment. It exists only for the opt-in live authority-context test.

## Tracking

Also flagged inline as a decisions-log line item back to the user in this
session, in case a separate decisions log is being kept outside this repo.
