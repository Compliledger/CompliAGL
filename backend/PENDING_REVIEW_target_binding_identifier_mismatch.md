# Pending review: `target` binding resolves to the wrong identifier for Gateway-style connectors

**Status:** NOT APPLIED. Found and written up 2026-08-17 during SecureRob pilot
debugging; deliberately held for fresh review rather than applied same-night.
Nothing in this document has been implemented.

**2026-08-17 update: `TARGET_MISMATCH` is now confirmed as the live, actual
blocker via real collected evidence — not just a theoretical concern.** See
"Confirmation update" section near the end of this document for the full
empirical evidence, including a ruled-out alternative hypothesis
(`allowed_issuers: []`) that was checked and eliminated along the way. Short
version: two fresh, back-to-back live runs through the real Gateway ->
CompliAGL pipeline, with real (non-synthetic) Gateway-collected perception
evidence, both produced `checks.target_binding = False` /
`EVIDENCE_TARGET_MISMATCH` / decision `DENIED`/`MANDATORY_CONTROL_FAILED` —
exactly as this document predicted, and with nothing else in the pipeline
now in question. This document's analysis and proposed direction were
already correct before this update; this just upgrades the evidence behind
them from "one replayed evidence item" to "two independent live runs,"
and removes an alternative explanation that had to be checked first.

**Repo:** `CompliAGL-repo/backend`
**File in question:** `app/services/evidence/evidence_orchestration_service.py`,
function `_resolve_binding` (~line 124-141), and its downstream consumer in
`build_plan` (~line 204-215).

---

## Context: how this was found

While confirming a smaller, already-applied fix — the SecureRob trial
package's `EV-SECUREROB-PERCEPTION` evidence requirement declared
`"target_binding": "target_id"`, which is not a recognized binding token
(`_resolve_binding` only recognizes `"actor"`, `"target"`,
`"intent"`/`"transaction"`), so it silently resolved to `None` and the
`target_binding` validation check was skipped (`null`) for every item,
never actually verified. That part is fixed and registered as trial package
`0.0.7-trial-localdev` (`target_binding: "target"`), and confirmed working:
`build_plan` now correctly resolves a real `target_id` into the task and
into `provenance.requirement.expected_target_id` instead of `None`.

While confirming that fix actually worked, I went further and replayed real,
previously-collected SecureRob evidence (job `24d53833`, a genuine
Gateway-collected item, not synthetic data) through
`evidence_validation_service.evaluate()` with only the corrected
`expected_target_id` applied, to see what the now-active check would
actually produce:

```
BEFORE (target_binding: "target_id" bug):  target_binding = null,  outcome STALE
AFTER  (target_binding: "target" fix):     target_binding = False, outcome TARGET_MISMATCH

raw.target_id (reported by the Gateway's connector):  ead9ab76-8eac-457c-a89d-9ae006847a65
expected_target_id (resolved by CompliAGL for the check): ca095d89-d8a9-4d00-b315-5177b17a7817
```

## The actual finding

Those two values will **never** match, for **any** resolution using this
connector, as currently wired — not a data bug, a structural one:

- `ead9ab76-...` is CompliAGL's own `Target.external_identifier` for this
  target (confirmed directly against the `targets` table) — this is the
  identifier the Gateway/robot actually knows itself by, and it's what the
  `SecureRobPerceptionConnector` reports back as `target_id` in its
  `CollectResult` (`securerob.py`, `target_id=data.get("target_id")` — the
  Gateway's own value, passed through faithfully).
- `ca095d89-...` is CompliAGL's own `Target.id` — the internal primary key.
  `_resolve_binding()` resolves the `"target"` token straight to
  `evidence_set.target_id`, which is the canonical `PolicyResolution`'s
  `target_id` field — i.e. the internal PK. It never looks up the `Target`
  row's `external_identifier`.

So `_resolve_binding("target", ...)` and this connector's `CollectResult`
are populated from two different identifier namespaces by construction. No
change to package config or evidence data can make them agree; only a code
change to what `_resolve_binding`/`build_plan` treats as the "expected
target" for this comparison would.

## What breaks once the token-typo fix takes effect

The token fix (`target_binding: "target_id"` → `"target"`) is itself
correct and already applied/published (`0.0.7-trial-localdev`) and mirrored
in the Gateway repo's `trial_register_policy.py`. But applying it changes
`target_binding` from a **silently-skipped, harmless `null`** into an
**actively-evaluated, always-`False` check** for this connector.

`evidence_validation_service._decide()` checks `target_binding` (returns
`TARGET_MISMATCH`) *before* `expiration`/`freshness` in its precedence
order. So: right now, the pipeline's actual blocker is a separate, unrelated
Gateway-side timing issue (evidence capture-vs-queryable-availability race,
documented separately) that manifests as `NOT_FOUND` or `STALE`. **The
moment that timing issue is fixed and evidence actually gets collected
fresh, this target-binding mismatch will immediately become the new,
permanent blocker** (`TARGET_MISMATCH` instead of `STALE`) — for the
SecureRob evidence requirement, and for anything else that uses
`target_binding: "target"` against a connector that reports an external
identifier rather than CompliAGL's internal PK.

## Blast radius (checked, not yet acted on)

`grep`'d the whole test suite for `"target_binding": "target"` — it's used
in two other places, both under the `EV_EXECUTION` / `execution_result`
evidence type (`tests/test_evidence_layer.py:180`,
`tests/test_control_assessment.py:169`). Both rely on the **current**
semantics: their fixtures build the simulator's `CollectResult.target_id`
directly from `target.id` (CompliAGL's internal PK) — see
`tests/test_evidence_layer.py:257`, `target_id=target.id` — i.e. these
existing tests pass specifically *because* both sides currently agree on
using the internal PK. **A blanket change to make `"target"` resolve to
`Target.external_identifier` instead would very likely break these existing
tests**, unless their simulator fixtures are updated in the same change, or
unless the resolution is made conditional (e.g. per-connector, or falling
back to `external_identifier` only when the internal `target_id` doesn't
match and a target record's `external_identifier` does).

This means the fix is not a one-line, contained change — it needs a
decision on:

1. Whether `"target"` should uniformly mean `external_identifier` now (and
   the two existing execution-result tests/simulators get updated to
   match), or
2. Whether there should be two distinct binding tokens (e.g. `"target"` for
   the internal PK, `"target_external_id"` or similar for the external
   identifier), so connectors that report their own external ID (like
   SecureRob's Gateway) and connectors that already agree on the internal
   PK (like the execution-result simulators) can each declare the right
   one, or
3. Some other design not yet considered.

## Proposed direction (not applied, for review)

Leaning toward option 2 above — a second, explicit binding token — since it
doesn't require touching the two existing, currently-correct
execution-result tests/simulators, and makes the identifier space a
requirement-author's explicit choice rather than an implicit assumption
baked into `_resolve_binding`. But this needs your review of the blast
radius above before any of it gets implemented, per your instruction
tonight. Nothing in this document has been applied.

---

## Confirmation update (2026-08-17, later same night): live-tested, not just replayed

The original finding above was based on replaying **one** previously-collected
evidence item (job `24d53833`) through `evidence_validation_service.evaluate()`
offline. That was enough to prove the identifier-namespace mismatch exists in
principle, but it left two things unconfirmed: (1) whether some other,
unrelated config difference (`allowed_issuers`) could be part of what was
observed, and (2) whether this reproduces on a **live**, end-to-end run
through the real Gateway -> CompliAGL pipeline, with evidence collected
fresh (not replayed), rather than only via manual offline replay.

Both are now confirmed, as a side effect of a separate, unrelated empirical
test (documented in `FINDING_allowed_issuers_empty_list_semantics.md`) that
happened to exercise this exact code path twice, live, back-to-back.

### What was tested and why it's relevant here

That test registered a new trial package version
(`0.0.8-trial-localdev-allowed-issuers-test`, package id
`b60dc69b-63e2-4bb4-bc2b-8e068f94feb4`) identical to the then-current
`0.0.7-trial-localdev` (package id `6d7c132b-6dcc-49f1-923a-01e260bdc974`,
the one with the `target_binding: "target"` token fix already applied)
except for `EV-SECUREROB-PERCEPTION.allowed_issuers`: `[]` vs.
`["compliagl-execution-gateway"]`. It then ran two fresh live requests
through the real Gateway (`:8080`) -> CompliAGL (`:8000`) pipeline —
`POST /api/v1/connectors/securerob/executions` -> policy-resolution ->
applicability-evaluation -> evidence-collection (retried once past a
separate, unrelated `NOT_FOUND` capture-timing race — see that finding doc
for detail) -> `decide()` — using genuinely fresh, Gateway-collected
perception evidence each time, not synthetic or replayed data.

Full artifacts: `CompliAGL-Execution-Gateway/trial_test_allowed_issuers.py`
(script), `CompliAGL-Execution-Gateway/trial_allowed_issuers_result.md`
(full request/response log, including the retry), and
`FINDING_allowed_issuers_empty_list_semantics.md` (write-up).

### Ruled out: `allowed_issuers: []` is not a contributing factor

Both runs' persisted `EvidenceValidationResult.checks`:

| | Run A (`allowed_issuers=[]`) | Run B (`allowed_issuers=["compliagl-execution-gateway"]`) |
|---|---|---|
| `raw.issuer` | `compliagl-execution-gateway` | `compliagl-execution-gateway` |
| `checks.issuer_trust` | `True` | `True` |
| `checks.target_binding` | `False` | `False` |
| `validation outcome` | `TARGET_MISMATCH` | `TARGET_MISMATCH` |
| `decision outcome` | `DENIED` (`MANDATORY_CONTROL_FAILED`) | `DENIED` (`MANDATORY_CONTROL_FAILED`) |

`issuer_trust` is `True` in both, and `evidence_validation_service._decide()`
checks `issuer_trust` (-> `UNTRUSTED_SOURCE`) *before* `target_binding`
(-> `TARGET_MISMATCH`) in its precedence order — so if `allowed_issuers` had
been masking or contributing to the mismatch result in either run, it would
have shown up as a *different* outcome one precedence step earlier in Run A
than Run B. It didn't: both runs are identical on every check except the one
under test, and both independently reach `target_binding = False` for the
same structural reason described earlier in this document. This rules out
`allowed_issuers` semantics as an alternative or contributing explanation
for the target-binding failure — it is not.

### Confirmed live, not just replayed

Both runs' raw evidence (`b1636489-0ea2-43e5-bfa8-2d20848bd950` for Run A,
`8a808c48-d548-42df-a6ee-694273c11195` for Run B) was collected fresh via
the real `SecureRobPerceptionConnector` against the real running Gateway —
`provenance.collected_via = "connector"`, `provenance.is_mock = false`,
`collection_status = "COLLECTED"` — during this session, not replayed from
the earlier `24d53833` job. Both show the exact same structural mismatch
this document already predicted:

* `raw_evidence.target_id` (both runs): `9e03e7fc-9f48-4b52-a7a6-a39685d7614e`
  — the Gateway's own value for the target, reported faithfully by
  `SecureRobPerceptionConnector` as `raw.target_id` (this is
  `Target.external_identifier` in CompliAGL's own `targets` table).
* `provenance.requirement.expected_target_id` (Run A):
  `d8b6464e-9a13-4656-9188-9eae28450848`; (Run B):
  `b8740285-3d0b-4b60-b5a3-104ec59c8a7c` — different per run only because
  each run's trial script created a fresh `Target` row via
  `POST /api/v1/targets` (per-run isolation, not a control variable);
  in both cases this is `_resolve_binding("target", ...)` resolving straight
  to `evidence_set.target_id`, CompliAGL's own internal PK for that run's
  `Target` row.
* These two values structurally can never match, for any run, exactly as
  predicted — confirmed twice more, independently, live.

### Net effect on this pending review

Nothing about the diagnosis or the proposed direction above changes. What
changes is confidence: the `TARGET_MISMATCH` blocker is no longer "found via
one offline replay of an old evidence item" — it is now confirmed, twice,
live, through the real pilot pipeline with genuinely fresh Gateway-collected
evidence, with the leading alternative-explanation candidate
(`allowed_issuers`) explicitly checked and ruled out. Whoever picks this up
can treat the root cause as settled and go straight to deciding between the
two options in "What breaks once the token-typo fix takes effect" above (or
proposing a third) — no further diagnostic work should be needed before
implementing a fix.

As a secondary, incidental confirmation: both live runs' `decide()` calls
returned real, non-stale `DENIED` outcomes (not `ESCALATED`/
`ASSESSMENT_NOT_EVALUABLE`) once evidence was actually collected — i.e. the
stale-cache bug from `BUG_REPORT.md` (fixed in commit `4bd15c2`, prior to
this session) is still confirmed fixed; it did not resurface or interfere
with this test.
