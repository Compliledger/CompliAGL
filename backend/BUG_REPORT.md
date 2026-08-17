# Bug Report: SecureRob pilot cannot reach APPROVED end-to-end

**Date:** 2026-08-16
**Found by:** live debugging of the SecureRob pilot integration (Gateway repo:
`securerob-pilot-integration` branch, commit `474ce48`)
**Status:** Gateway-side fix (applicability-evaluations) is committed and
confirmed working. The remaining blocker is a bug in the CompliAGL backend
(`CompliAGL-repo/backend`) — **not** a Gateway-side gap, see "Correction"
below. Root-caused via direct API-level and source-level investigation, not
guessed at.

---

## Context: how this was found

The Gateway's `compliagl.py` was recently fixed to call
`POST /api/v1/applicability-evaluations` (a required-but-nothing-auto-triggers
CompliAGL pipeline stage) before evidence collection. After applying that fix,
committing it (`474ce48`), and pushing it, I ran the real end-to-end pilot
request through two live servers (Gateway on `:8080`, CompliAGL backend on
`:8000`):

```python
POST http://127.0.0.1:8080/api/v1/connectors/securerob/executions
{
  "robot_id": "securerob-alpha",
  "action": "perform_karate_demonstration",
  "skill_id": "karate.v1",
  "intensity": 0.5,
  "dry_run": false,
  "actor_id": "u1",
  "perception": {
    "snapshot_id": "snap-evidence-test",
    "observed_at": "<now, UTC ISO8601>",
    "confidence": 0.95,
    "person_detected": false,
    "person_in_action_envelope": false,
    "nearest_person_distance_m": 5.0,
    "object_detected": false,
    "object_in_action_envelope": false,
    "robot_connected": true,
    "emergency_stop_active": false
  },
  "requested_at": "<now>",
  "correlation_id": "evidence-test-18",
  "idempotency_key": "evidence-test-key-18"
}
```

Response:

```json
{
  "decision": "ESCALATED",
  "dispatched": false,
  "state": "ESCALATED",
  "execution_id": "99b665af-1381-5f34-9c20-495cb1b74075",
  "correlation_id": "evidence-test-18"
}
```

Not `ALLOW`/`APPROVED`. Everything below documents tracing this down to its
actual root cause, including one important **self-correction**: my first
hypothesis (stated to the user before this write-up) was wrong, and I want
that on record rather than quietly overwritten.

### Important caveat discovered mid-investigation: the first live test was invalid

While tracing the failure, I discovered the Gateway process that had been
listening on `:8080` for this entire debugging session (PID 9744) had a
**process start time of `2026-08-16 20:57:54` IST**, which is *before* the fix
commit at `2026-08-16 23:25:16` IST. It was a stale process left listening on
the port from earlier in the session, silently serving every request with the
**pre-fix** `compliagl.py` (confirmed: attempting to start a fresh `uvicorn`
on the same port failed with `[WinError 10048] only one usage of each socket
address...`, which is what tipped this off).

I killed PID 9744, started a genuinely fresh Gateway process (confirmed via
`wmic process ... get CreationDate` that its start time, `23:47:13` IST, is
after the fix commit), and reran the live request end-to-end with a new
`correlation_id`/`idempotency_key` (`evidence-test-19`). Result was still
`ESCALATED`, but this time I confirmed (via CompliAGL's own
`GET /api/v1/applicability-evaluations?policy_resolution_id=...`) that
`/api/v1/applicability-evaluations` **had** actually been called and had
persisted `APPLICABLE` for all 5 requirements — proving the fix itself is
working correctly, and that the remaining `ESCALATED` outcome is a **separate,
new issue**, not a symptom of the applicability fix failing or of the stale
process. All findings below are from this second, clean run
(`policy_resolution_id = d17d7857-dd50-444e-9806-dd7c500c4a2a`), cross-checked
against the first, tainted run
(`policy_resolution_id = 858d91ae-e50d-45ae-a311-99c225b5809a`) where
relevant.

---

## Issue 1: CompliAGL's canonical pipeline stages cache their first result forever, even when it was computed from incomplete upstream data

**Repo:** `CompliAGL-repo/backend`
**This is the actual, confirmed root cause of the `ESCALATED` result.**

### Files and functions involved

| # | File | Function | Lines |
|---|------|----------|-------|
| 1 | `app/services/canonical/decision_service.py` | `decide_for_resolution` (assessment reuse) | 285–292 |
| 1a | `app/services/canonical/decision_service.py` | `_resolve_outcome` | 124–170 |
| 2 | `app/services/canonical/evidence_sufficiency_service.py` | `evaluate_or_get_for_resolution` | 366–373 |
| 3 | `app/services/canonical/control_determination_service.py` | `determine_or_get_for_resolution` | 302–315 |
| 4 | `app/services/canonical/evidence_requirement_service.py` | `resolve_or_get_for_resolution` | 324–337 |
| — | `app/services/evidence/evidence_collection_service.py` | `start_collection` | 52–98 (call site at 70–72) |

### What's wrong

All four of `decide_for_resolution`, `evaluate_or_get_for_resolution`,
`determine_or_get_for_resolution`, and `resolve_or_get_for_resolution` follow
the identical pattern:

```python
existing = <look up the most recent record for this policy_resolution_id>
if existing is not None:
    return existing
return <compute fresh, persist, return>
```

This is a "compute once per `policy_resolution_id`, reuse forever" cache. The
problem: **the cache key is existence, not input identity.** None of these
functions check whether the record they're about to reuse was actually
computed from the *current* upstream state (current applicability results,
current control determination, current evidence package). They just check "is
there any record at all for this `policy_resolution_id`" — and if the answer
is yes, they return it unconditionally, no matter how stale.

Each of these stages already computes a `input_hash` when it does the fresh
computation (see e.g. `decision_service.py:343-361`,
`evidence_sufficiency_service.py:305-319`,
`control_determination_service.py:240-258`,
`evidence_requirement_service.py:271-279`) — the machinery to detect "have my
inputs changed since I last computed this" already exists on every one of
these records, it's just never consulted before deciding to reuse a cached
row.

### Why this causes the observed bug

`POST /api/v1/evidence-collections` is implemented by
`evidence_collection_service.start_collection` (lines 52-98). Its very first
step, line 70-72:

```python
evidence_set = evidence_requirement_service.resolve_or_get_for_resolution(
    db, organization_id, policy_resolution_id
)
```

`resolve_or_get_for_resolution` (evidence_requirement_service.py:324-337), if
no `EvidenceRequirementSet` exists yet for this `policy_resolution_id`, calls
`resolve_for_resolution`, which itself (line 119-121) calls:

```python
control_set = control_determination_service.determine_or_get_for_resolution(
    db, org, resolution.id
)
```

So a **single** call to `POST /api/v1/evidence-collections` transitively
triggers first-time computation and permanent caching of *both* the
`ApplicableControlSet` (control determination) *and* the
`EvidenceRequirementSet` (evidence requirement resolution) for that
`policy_resolution_id` — whatever they resolve to on that first call is locked
in forever.

Separately, `POST /api/v1/decisions/decide` → `decide_for_resolution` (lines
285-292) does the same thing one layer up for the `Assessment`: the first time
`decide()` is ever called for a `policy_resolution_id`, it triggers
`assessment_service.assess_for_resolution`, which itself calls
`control_evaluation_service.evaluate_for_resolution`, which calls
`evidence_sufficiency_service.evaluate_or_get_for_resolution` (same
cache-forever pattern, evidence_sufficiency_service.py:366-373). Whatever
`Assessment.overall_result` comes out of that first call
(`SATISFIED`/`NOT_SATISFIED`/`NOT_EVALUABLE`/`MANUAL_REVIEW_REQUIRED`) is
permanently pinned to that `policy_resolution_id`.

`_resolve_outcome` (decision_service.py:124-170) checks the (possibly stale,
cached) assessment outcome **before** it ever looks at what the decision
conditions evaluated to:

```python
if assessment_outcome == A.NOT_EVALUABLE.value:
    # NOT_EVALUABLE can never silently become APPROVED.
    return D.ESCALATED.value, ["ASSESSMENT_NOT_EVALUABLE"]
...
if condition_outcome == D.APPROVED.value:
    return D.APPROVED.value, ["APPROVED_BY_POLICY"]
```

So once a `policy_resolution_id` has ever been assessed as `NOT_EVALUABLE`
(which is exactly what happens on a normal, single synchronous pass through
`evaluate_governance` — evidence collection, evidence sufficiency, and
assessment all get computed for the very first time, in sequence, within
milliseconds of each other, and something about that first pass is
apparently not yet fully consistent — see "Open question" below), it can
**never become `APPROVED` again for that `policy_resolution_id`**, no matter
how many times you correctly re-run every downstream stage afterward.

### Complete repro steps

All requests below are direct calls to CompliAGL's own API
(`http://127.0.0.1:8000`), bypassing the Gateway entirely, using the
`policy_resolution_id` from the **clean, post-restart** live test:
`d17d7857-dd50-444e-9806-dd7c500c4a2a` (org: `default-org`).

1. **Confirm the Gateway's live request already ran applicability correctly**
   for this resolution:
   ```
   GET /api/v1/applicability-evaluations?organization_id=default-org&policy_resolution_id=d17d7857-dd50-444e-9806-dd7c500c4a2a
   ```
   → 5 rows, all `result: APPLICABLE`, `reason_codes: ["APPLICABLE_BY_CRITERIA"]`,
   `evaluated_at` timestamps matching the live request's timing.

2. **Retry evidence collection** for the same resolution (no other manual
   steps beforehand — no control-determinations, no evidence-requirement-resolutions):
   ```
   POST /api/v1/evidence-collections
   {"organization_id": "default-org", "policy_resolution_id": "d17d7857-dd50-444e-9806-dd7c500c4a2a", "production_mode": true}
   ```
   → `201`, `"status": "COMPLETED"`, `"failures": []`, `"unresolved": []`,
   `"raw_evidence_ids": ["0675f424-dd53-4c56-9d9c-64b8df64effe"]`,
   `"reason_codes": ["EVIDENCE_COLLECTION_COMPLETED"]`.

   This proves the evidence pipeline (control determination → evidence
   requirement resolution → connector call to the Gateway's real perception
   endpoint → validation → normalization → package assembly) works completely
   correctly when invoked directly, on this exact resolution, with this exact
   data.

3. **Retry the decision** for the same resolution, immediately after step 2:
   ```
   POST /api/v1/decisions/decide
   {"organization_id": "default-org", "policy_resolution_id": "d17d7857-dd50-444e-9806-dd7c500c4a2a"}
   ```
   → `201`,
   ```json
   {
     "outcome": "ESCALATED",
     "reason_codes": ["DECISION_ESCALATED", "ASSESSMENT_NOT_EVALUABLE", "POLICY_OK"],
     "decision_conditions_triggered": [
       {"condition_id": "COND-ALL-CLEAR", "resulting_decision": "APPROVED", "reason_code": "POLICY_OK", "priority": 1000, "terminal": true}
     ],
     "evidence_package_id": "dbf1eddc-3c7d-491c-80f0-0db841e90003",
     "evidence_package_hash": "74c4e5ed3f20603c5fd8a26826e5f65399b19a09c40836bf135a59158eb463d0",
     "prior_decision_id": "4200c67e-4df6-4705-9587-d89a6d4e7fa7",
     ...
   }
   ```

   This is the smoking gun: `evidence_package_id` correctly points at the
   *freshly completed* evidence package from step 2, and
   `decision_conditions_triggered` correctly shows the policy's
   `COND-ALL-CLEAR` condition fired with `resulting_decision: APPROVED`. But
   the top-level `outcome` is still `ESCALATED`, with `ASSESSMENT_NOT_EVALUABLE`
   — because `decide_for_resolution` reused the `Assessment` row created by the
   *original* `decide()` call (embedded in the Gateway's request, run before
   step 2's fresh evidence collection existed), never recomputing it.

   The exact same behavior was independently reproduced on the first (tainted,
   pre-fix-process) test's resolution, `858d91ae-e50d-45ae-a311-99c225b5809a`,
   after manually running `control-determinations` →
   `evidence-requirement-resolutions` → `evidence-collections` (all
   succeeding) → `decide` (still `ESCALATED`/`ASSESSMENT_NOT_EVALUABLE`) — so
   this is not specific to one resolution or one code path into the bug.

### Open question (not yet root-caused, doesn't block the fix)

I was not able to fully pin down *why* the very first, synchronous pass
through `evaluate_governance` (applicability → evidence-collections → decide,
all three calls seconds apart, all against the same already-correct
applicability data) produces an incomplete/`NOT_EVALUABLE` assessment on the
first try, when replaying the identical `evidence-collections` call
afterward succeeds cleanly. Candidates I was not able to fully rule in or out
without adding instrumentation to CompliAGL (which I did not do, since this
is out of scope for a read-only investigation):

* A transient failure on the very first real network call from CompliAGL's
  `securerob-perception-gateway` connector to the Gateway (retried
  successfully by hand moments later).
* Some other timing/ordering sensitivity in how `evidence_sufficiency_service`
  or `control_evaluation_service` reads the evidence package on the very
  first computation.

This is worth root-causing in its own right, but **it doesn't change the
fix**: regardless of why the first pass is occasionally imperfect, a
transient hiccup on a physical-safety-relevant decision pipeline should be
*retryable*, not permanently fatal to that intent. The caching bug is what
turns a transient/first-pass issue into a permanent one.

### Proposed fix

The module docstrings already state the intended design: *"Deterministic —
identical inputs and package versions always produce the same decision
hash"* (`decision_service.py:11-14`). The bug is that "safe to reuse" is
currently keyed on **existence** ("has this resolution ever been processed
by this stage?") instead of **input identity** ("do the current upstream
inputs match what this cached record was computed from?"). Every stage
already computes an `input_hash` for exactly this purpose; it's just not
being used to invalidate the cache.

Apply the same fix at all four sites:

1. **`evidence_sufficiency_service.evaluate_or_get_for_resolution`** — before
   reusing `existing`, recompute the current input hash (same fields as
   `evaluate_for_resolution`'s `input_hash`, i.e. the current
   `CanonicalEvidencePackage.id`/`package_hash` and
   `EvidenceRequirementSet.id`/`result_hash`) and compare against
   `existing.input_hash`. Reuse only on a match; otherwise call
   `evaluate_for_resolution` fresh.
2. **`control_determination_service.determine_or_get_for_resolution`** — same
   approach, keyed on the current applicability-evaluation result set feeding
   it.
3. **`evidence_requirement_service.resolve_or_get_for_resolution`** — same
   approach, keyed on `control_set.result_hash`.
4. **`decision_service.decide_for_resolution`** — stop special-casing
   "assessment is `None`"; always call `assessment_service.assess_for_resolution`.
   Once (1)-(3) are fixed to only reuse on a genuine input match, this call
   will itself cheaply short-circuit to cached data when nothing has actually
   changed (since `assess_for_resolution`'s own dependencies won't have
   changed), and correctly recompute when something upstream has.

This preserves the stated determinism guarantee (identical inputs still
short-circuit to the same cached row and hash) while fixing the actual
defect: a `policy_resolution_id` is no longer permanently pinned to whatever
any stage happened to compute on its first, possibly-premature invocation.

### Suggested regression test

1. Create a policy-resolution.
2. Call `decide()` before evidence exists (or before control-determination has
   a full applicability basis) → assert `ESCALATED` / `ASSESSMENT_NOT_EVALUABLE`.
3. Resolve applicability, run control-determination, evidence-requirement-resolution,
   and evidence-collection to completion (`status: COMPLETED`).
4. Call `decide()` again on the **same** `policy_resolution_id` → assert
   `APPROVED`, not a repeat of step 2's stale result.

---

## Issue 2: Gateway `compliagl.py` — corrected finding (originally reported as a missing control-determinations call; superseded)

**Repo:** `CompliAGL-Execution-Gateway` (this repo)
**File:** `app/clients/compliagl.py`
**Function:** `CompliAGLClient.evaluate_governance` (class starts line 77,
method starts line 136)

### What I originally reported (and why it was wrong)

In my first pass at diagnosing the `ESCALATED` result (on the *tainted* test,
`858d91ae`, before I discovered the stale-process issue above), I found that
manually calling `POST /api/v1/control-determinations` was necessary to get
`evidence-collections` to stop returning `UPSTREAM_UNRESOLVED_REQUIREMENT`. I
concluded from this that `evaluate_governance` needed an explicit call to
`/api/v1/control-determinations` between the applicability-evaluations call
(lines 270-277) and the evidence-collections call (lines 295-303), mirroring
the same "nothing downstream auto-triggers this" pattern as the
applicability fix.

**This conclusion does not hold up.** Reading
`evidence_collection_service.start_collection` (see Issue 1 above) shows that
`POST /api/v1/evidence-collections` already internally calls
`evidence_requirement_service.resolve_or_get_for_resolution`, which itself
calls `control_determination_service.determine_or_get_for_resolution` if no
`ApplicableControlSet` exists yet. **Control determination is already
auto-triggered on demand by evidence collection** — there is no missing call
here. The reason my manual retry needed an explicit `control-determinations`
call on the *tainted* test was specifically because that test's `policy_resolution_id`
already had a **wrong, cached `INDETERMINATE` `ApplicableControlSet`** baked
in from the very first (pre-fix, no-applicability-data) `evidence-collections`
call — i.e., it was hitting Issue 1's caching bug, not a Gateway-side gap.
Calling `/control-determinations` directly (which is *not*
memoized — see `determine_for_resolution`, called unconditionally by the
route) happened to produce a fresh, correct row that got picked up afterward
— but that's a workaround for Issue 1, not evidence of a separate Gateway gap.

### What actually remains true

On the *clean* test (`d17d7857`, genuinely fresh Gateway process running the
committed fix), `compliagl.py`'s single call sequence
(policy-resolution → applicability-evaluations → evidence-collections →
decide, lines 241-318) is **not** missing any stage — every stage that needs
to run does get triggered, either directly or transitively. The `ESCALATED`
result on this clean run is fully and exclusively explained by Issue 1.

**No code change is currently indicated in `app/clients/compliagl.py` for
this.** I'm leaving this section in the report specifically so the
correction is on record, rather than silently dropping the original
(incorrect) hypothesis — in case Issue 1's fix, once applied, still leaves
some edge case where an explicit control-determinations call turns out to be
useful (e.g. as a way to force-refresh a cached-but-stale control set without
waiting for input-hash comparison logic), it's worth revisiting once Issue 1
is fixed and retested.

### Repro steps (for completeness — showing the current call sequence is correct)

Relevant excerpt of `app/clients/compliagl.py`, lines 241-318 (current,
committed state):

```python
# Step 3: Create the Policy Resolution
resolution_resp = await self._http.post("/api/v1/policy-resolutions", json=resolution_payload)
resolution_resp.raise_for_status()
policy_resolution_id = str(resolution_resp.json().get("id", ""))

# Step 3a: Explicitly run applicability evaluation.
applicability_resp = await self._http.post(
    "/api/v1/applicability-evaluations", json=applicability_payload
)
applicability_resp.raise_for_status()

# Step 3b: Start the evidence pipeline
evidence_resp = await self._http.post(
    "/api/v1/evidence-collections", json=evidence_payload  # production_mode=True
)
evidence_resp.raise_for_status()

# Step 4: Run CompliAGL's deterministic decision engine
decide_resp = await self._http.post("/api/v1/decisions/decide", json=decide_payload)
decide_resp.raise_for_status()
```

Live test, clean run:

1. `POST /api/v1/connectors/securerob/executions` on the Gateway (`:8080`)
   with `correlation_id: evidence-test-19` → `202`,
   `{"decision": "ESCALATED", "execution_id": "086b55c8-19b9-5a76-b54f-a2df56e5942f", ...}`.
2. `GET /api/v1/executions/086b55c8-19b9-5a76-b54f-a2df56e5942f` on the
   Gateway → `governance_response.metadata.policy_resolution_id =
   d17d7857-dd50-444e-9806-dd7c500c4a2a`.
3. `GET /api/v1/applicability-evaluations?policy_resolution_id=d17d7857-...`
   on CompliAGL (`:8000`) → 5 rows, all `APPLICABLE`, timestamped at the
   request time — proves `evaluate_governance`'s Step 3a ran and succeeded.
4. See Issue 1's repro steps 2-3 above for what happens next.

---

## Summary for whoever picks this up

* **Gateway-side (this repo):** nothing further to do right now. The
  applicability-evaluations fix (commit `474ce48`) is correct and complete;
  the call sequence in `evaluate_governance` is not missing a stage.
* **CompliAGL backend:** the real, confirmed blocker is Issue 1 — four
  "compute once per `policy_resolution_id`, reuse forever" caches
  (`decision_service.py:285-292`, `evidence_sufficiency_service.py:366-373`,
  `control_determination_service.py:302-315`,
  `evidence_requirement_service.py:324-337`) that should be keyed on input
  identity (`input_hash` comparison) rather than mere existence. Until that's
  fixed, **any** `policy_resolution_id` that gets assessed even slightly too
  early in its lifecycle is permanently stuck at `ESCALATED`/`DENIED`, no
  matter how correct everything is afterward — which is a real risk for a
  physical-safety pilot where evidence collection is a live network call that
  can legitimately be slow on a first attempt.
