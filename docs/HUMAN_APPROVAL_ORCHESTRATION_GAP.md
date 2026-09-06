# Gap: human-approval orchestration for ESCALATED decisions

**Status: RESOLVED (2026-09-06).** 4c now runs and is evidenced in
`demo3_step2/compliagl_scenarios_results.json` (+ `4c-neg-wrong-approver`,
`4c-neg-expired-approval`). The design below was built as it was sketched:

| gap-doc item | built as |
|---|---|
| #1 no authority check on the approver | `authority_context_service.verify_approver_authority` + `escalation_approval_service.submit` — live `approve` probe, `sufficient == true` + approver `principal_type == HUMAN` + a cross-check against `Decision.required_approver_types` (distilled from CompliIdentity's own `applicable_approvals`) |
| #2 escalation-approval finding didn't require a review | new `FindingType.ESCALATION_APPROVAL_REQUIRED` — always remediation-INELIGIBLE, never `VALIDATED`, and `reassessment_service.trigger()` refuses it (three barriers) |
| #3 no approval expiry | `EscalationApproval.valid_until` (default `ESCALATION_APPROVAL_TTL_SECONDS`); `approval.expired` runtime fact; an expired approval does not upgrade |
| #4 no wrong-actor / wrong-action rejection at the approval layer | `submit()` requires a CURRENT `ESCALATED_BY_POLICY` decision and rejects self-approval; wrong action is forced (`action="approve"`); type mismatch is `approver_type_mismatch` |
| `ReviewType.ESCALATION_APPROVAL` wired to nothing | superseded — the dedicated `EscalationApproval` model is the first-class record |
| package-approval layer (below) | `GOVERNANCE_APPROVAL_AUTHORITY_REQUIRED` + `governance_package_service.approve(*, approver_principal_id, rationale)` — no more free-form string; verified against CompliIdentity (`governance.package` / `approve`) when the flag is set, fail-closed |

The re-decision is package-authored (`_resolve_outcome` unchanged): HarborStone
package **v1.1.0** adds `DC-HARBORSTONE-APPROVED-VIA-HUMAN`. The rest of this
document is the original analysis, kept for context.

---

**Original status:** Open. Blocked Fix Order step 2 acceptance criterion **4c**
only. 4a, 4b, 4d and 4e ran and were evidenced. The Fix Order itself lists
"complete human-approval orchestration" as incomplete; this document
records exactly what was missing, so it is not rediscovered from scratch
next time.

## What 4c asks for

> Jordan submits a valid approval for the escalated decision → CompliAGL
> re-evaluates and reaches APPROVED, **with the first decision preserved and
> a new decision created**.

Concretely, for the HarborStone scenario:

1. AIRA's $250k proposal escalates (proven — scenario 4b: ESCALATED /
   `HUMAN_APPROVAL_REQUIRED`, real CompliIdentity `approval_required: true`).
2. Jordan Lee — who holds `aml.action:approve` scoped to the case in
   CompliIdentity (proven — setup probe AC3: `sufficient: true`) — records
   an approval of *that specific escalated decision*.
3. CompliAGL verifies Jordan's authority to approve **at approval time**,
   then produces a **new** `Decision` (`APPROVED`), marks the escalated one
   `SUPERSEDED`, and links them (`prior_decision_id` /
   `superseded_by_decision_id`).
4. Only then can an `ExecutionAuthorization` be issued.

## What already exists

| piece | file | status for 4c |
|---|---|---|
| Decision-supersession primitive: `decide_for_resolution(..., prior_decision_id=)` preserves the prior decision, creates a new immutable one, links both ways | `decision_service.py` | ✅ the low-level mechanism works |
| Finding→resolution→re-assessment chain: a *validated* finding resolution produces a new `APPROVED` decision preserving the prior | `reassessment_service.trigger()` | ⚠️ remediation-shaped, not approval-shaped — see below |
| Review record with reviewer identity: `ReviewRecord{reviewer_id, reviewer_role, review_type, outcome}` | `review_service.record()` | ⚠️ stores the fields; enforces nothing |
| `ReviewType.ESCALATION_APPROVAL` enum value | `canonical_enums.py` | ❌ defined; referenced by **zero** lines of logic |

## What is missing

### 1. No authority check on the approver

`review_service.record()` accepts any `reviewer_id` string. Nothing calls
CompliIdentity to confirm the reviewer holds `aml.action:approve` (or any
grant) for the case. The entire point of wiring this step to CompliIdentity
— that Jordan's approval authority is real, scoped and revocable — is not
exercised on the approval path. A revoked or unauthorised "approver" would
be accepted.

### 2. An escalation-approval finding does not structurally require a review

`resolution_validation_service.validate()` only sets `review_needed` — and
therefore only requires an approving `ReviewRecord` — when
`finding.finding_type == MANUAL_REVIEW`. A decision that escalated via a
`HUMAN_APPROVAL_REQUIRED` decision condition produces a `FindingType.OTHER`
finding (`finding_service.generate_for_decision` → "unattributed"
fallback). For an `OTHER` finding the resolution validates on submitted
*resolution evidence* alone (a remediation plan's required evidence types,
or any one VALID resolution-evidence item) — **no reviewer identity and no
approval record are required at any point**. So the borrowed remediation
path would let an escalation clear with nobody having approved anything.

### 3. No approval expiry

There is no concept of a time-bounded approval. 4d's "expired approval
attempt → not APPROVED" cannot be tested because there is nothing that
issues, or ages out, an approval.

### 4. No wrong-actor / wrong-action rejection at the approval layer

`create_review` does not check that the reviewer is a *different* principal
from the actor, that the review targets the right decision, or that the
`review_type` matches the finding. (Wrong-actor / wrong-action *at the
decision layer* is covered — scenarios 4d-i/ii/iii — but that is a
different control point.)

## Related: the same class of gap at the package-approval layer

**Addressed (2026-09-06).** `governance_package_service.approve()` no longer
takes a free-form string: it requires `approver_principal_id` **and**
`rationale` and records both. When `GOVERNANCE_APPROVAL_AUTHORITY_REQUIRED` is
set, the approver's authority is verified against CompliIdentity
(`governance.package` / `approve`) via the shared
`verify_approver_authority` helper and the approval is rejected fail-closed
otherwise (`approver_authority_hash` binds the verified snapshot). The flag
defaults **off**, mirroring `GOVERNANCE_SIGNING_KEYS` (empty = not enforced) —
so `seed_harborstone_package()` still publishes in dev, but a locked-down
deployment with the flag on would (correctly) reject a seed-bootstrap
approver. Not done: an anti-self-approval check — the package model records
no author identity to compare against.

*Original text:* `approve(db, org, package_id, approved_by: str)` took a
free-form string and recorded it verbatim, with no check that it was a real
principal, held any authority, or differed from the author. This was
structurally the same defect as gaps 1 and 4 above.

## What a real design needs (sketch — not a specification)

- An **approval submission** endpoint/service: `(decision_id, approver_
  principal_id, rationale)` → verify the decision is currently `ESCALATED`;
  call CompliIdentity authority-context for `approver_principal_id` with the
  intent's real `resource` / `action: "approve"` / `resource_instance`;
  require `sufficient: true` (or the contract's approve-specific signal);
  reject otherwise.
- Persist an **approval record** distinct from `ReviewRecord` (or wire
  `ReviewType.ESCALATION_APPROVAL` into `resolution_validation_service` as a
  first-class, authority-checked case), with an explicit `valid_until`.
- On a valid, unexpired approval: call `decide_for_resolution(...,
  prior_decision_id=<escalated decision id>)` — but the re-decide needs a
  way to *know* the approval happened. Options: an `approval` fact in the
  runtime-facts context that a package decision condition can read
  (`approval.present == true and approval.approver_authorized == true`), or
  an engine-level branch analogous to the `AUTHORITY_CONTEXT_UNAVAILABLE`
  guard. The former keeps it package-authorable and consistent with how the
  rest of the engine works.
- Apply the same authority check to `governance_package_service.approve()`.

## Evidence

`demo3_step2/compliagl_scenarios_results.json` — **all 9 scenarios** (4a, 4b,
4c, `4c-neg-wrong-approver`, `4c-neg-expired-approval`, 4d ×3, 4e) pass against
the live CompliIdentity instance, with real request/response captured.
