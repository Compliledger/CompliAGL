# HarborStone Governance Package — Design Draft

**Status:** Draft for review. Not yet authored in CompliAGL. Written to be
handed to whoever authors it through CompliAGL's intake/validate/approve/
publish pipeline, or to a Claude Code session doing that authoring.

## Why this package needs to exist

CompliAGL's decision engine has no hardcoded thresholds — every outcome
comes from package-authored decision conditions evaluated against a
runtime-facts context. The only governance package currently seeded is an
unrelated demo travel-booking policy. For the $250K AML/sanctions scenario
to produce the right outcomes (APPROVED / DENIED / ESCALATED), a real
package has to be authored from scratch. This package is also the thing
that turns on the new CompliIdentity integration for this scenario, via
`requires_authority_context: true` — the demo travel-booking package and
all existing tests stay unaffected because that flag defaults `false`.

## Package-level settings

- `requires_authority_context: true` — required so `authority_context_service`
  actually gets called for this package's decisions. Without this flag, the
  new `facts["authority"]` context would be `UNAVAILABLE`-by-default-absence
  rather than a real fetched result.
- `resource` / `action` / `resource_instance` sent to CompliIdentity:
  **corrected 2026-09-06 against the live demo3 acceptance run** — see
  Resolved item 4 below. The earlier draft assumed a fixed `action:
  "request"` probe verb. CompliIdentity's real permission model keys on the
  semantic verb (`read` / `propose` / `approve`) *and* on
  `resource_instance` scoping. Every acceptance check used the real action
  plus `resource_instance: "HARBORSTONE-2024-0042"`. The HarborStone intent
  must therefore set, per decision step:
  - `intent.parameters["compliidentity_resource"]` — e.g. `"aml.case"`,
    `"aml.action"`, `"sanctions.screening"` (not a single `"transfer"`).
  - `intent.parameters["compliidentity_action"]` — the semantic verb.
  - `intent.parameters["compliidentity_resource_instance"]` — the case id,
    so CompliIdentity's per-case grant scoping (AIRA's grant scoped to one
    case, inherited by SENTRY through the delegation) is actually visible to
    the probe.
  `decision_service._authority_request_params()` reads all three; each falls
  back to prior behaviour when unset.

## Proposed decision conditions

Order matters — per the confirmed `_resolve_outcome()` semantics, a
terminal DENIED condition overrides everything, including a SATISFIED
assessment. Conditions below are listed in the intended evaluation
priority.

### 1. DENIED — authority actively revokes/blocks

```
condition: authority.reason in [
    "permission_missing",
    "delegation_revoked",
    "principal_not_active",
    "resource_scope_unmatched",
    "limit_exceeded",
]
outcome: DENIED
reason_code: AUTHORITY_DENIED
```

These are cases where CompliIdentity has positively told us the principal
cannot act — not "we couldn't find out," but "the answer is no." Fail-closed
here means DENIED, not a softer ESCALATED.

**List corrected 2026-09-06 against live CompliIdentity — see Resolved
item 4.** `credential_expired` was removed: it does not exist in
CompliIdentity's finding vocabulary (the model has no expiring-credential
concept for these principals). `resource_scope_unmatched` was added: it
*fired* in the acceptance run when SENTRY probed a case its delegated grant
was not scoped to — same failure class as `limit_exceeded` (a delegate
reaching outside its bounded authority), so it belongs on the DENIED list
by the same reasoning below. `authority.reason` is a single derived code
(`authority_context_service._derive_reason`), so `in [...]` still matches
exactly one value at a time.

**RESOLVED: `limit_exceeded` → DENIED.** Reasoning: in this scenario,
AIRA delegates a narrow, scoped sanctions-screening task to SENTRY;
`limit_exceeded` most likely means the delegate tried to act outside its
own granted scope, which is a different failure mode than "legitimate
transfer needing human sign-off." A delegate exceeding its bounded
authority shouldn't be silently escalated past at the decision layer — if
HarborStone wants an override path for this case, it should be a
re-delegation with a wider grant (through CompliIdentity, auditable), not
a human approving around a scope violation at decision time. If the real
business rule differs, this is a one-line change to move it into the
ESCALATED condition below instead.

### 2. ESCALATED — human approval required

```
condition: authority.reason == "approval_required"
           OR authority.approval_required == True
           OR (intent.amount_currency == "USD" AND intent.amount_minor >= 25000000)
outcome: ESCALATED
reason_code: HUMAN_APPROVAL_REQUIRED
```

This is the condition that gets Jordan Lee into the loop for the $250K
transfer, whether CompliIdentity itself says approval is required, or the
amount threshold alone triggers it. (Amount field corrected 2026-09-05 —
see Resolved item 3 below.)

The raw `authority.approval_required` boolean clause was added 2026-09-06:
CompliIdentity emits it directly (confirmed — AIRA's propose at exactly
$250,000.00 returned `approval_required: true`, at $249,999.99 returned
`sufficient: true`), and testing it alongside the derived
`authority.reason` keeps the condition correct even if `_derive_reason`'s
priority ordering is ever changed. CompliIdentity is in fact already
enforcing this exact threshold itself (`approval_thresholds.threshold:
"24999999"`), so the amount clause here is now defence-in-depth / the
fallback for when the probe is UNAVAILABLE, not the primary trigger.

**RESOLVED: `reason_code: HUMAN_APPROVAL_REQUIRED` on an ESCALATED
condition is the confirmed approach**, not just the likely one. Direct
precedent already exists in shipped code: `_resolve_outcome()`'s
`AUTHORITY_CONTEXT_UNAVAILABLE` guard uses exactly this pattern —
a `reason_code` on `ESCALATED`, not a fourth outcome value — in the same
file, already reviewed and merged. No engine change needed to support
this; just author the condition.

**Note:** `AUTHORITY_CONTEXT_UNAVAILABLE` does **not** need to be authored
here — that's handled at the engine level by the tightened
`_resolve_outcome()` guard (UNAVAILABLE downgrades an would-be-APPROVED
outcome to ESCALATED automatically). Don't duplicate that logic in the
package.

### 3. APPROVED — clean path

```
condition: assessment == SATISFIED
           AND authority.sufficient == true
           AND intent.amount_currency == "USD"
           AND intent.amount_minor < 25000000
outcome: APPROVED
reason_code: (none needed)
```

Only reachable if neither of the above conditions fired and the assessment
came back clean. (Amount field corrected 2026-09-05 — see Resolved item 3
below.)

### 4. Fallback

No explicit fallback condition needed — the engine's own fail-closed
default (`NO_DECISION_CONDITION_MATCHED` → DENIED) covers anything not
matched above. Worth a comment in the package source noting this is
intentional, not an oversight.

## Resolved (2026-09-05)

1. `limit_exceeded` → DENIED. See Section 1 above for reasoning.
2. `HUMAN_APPROVAL_REQUIRED` as a `reason_code` on ESCALATED (not a new
   engine outcome) — confirmed by precedent already shipped in
   `decision_service.py`. See Section 2 above.

3. **Amount field: `intent.amount_minor`, not `intent.parameters.amount`.**
   The original draft's conditions (Sections 2 and 3, prior version)
   referenced `intent.parameters.amount` — a field nothing in the engine
   ever populates. Confirmed against real source: `app/models/intent.py`
   documents `parameters` as "Structured parameters (JSON text) — **not** a
   flat amount/currency pair" (line 35), and both the model docstring
   (lines 9-10) and the `ExecutableGovernancePackageCreate` schema docstring
   independently state monetary values use integer minor units via
   `amount_minor`/`amount_currency`, never anything nested under
   `parameters`. `runtime_facts.build_intent_facts()` confirms this
   structurally too — `amount_minor` is a top-level sibling key of
   `parameters`, not a field inside it. As drafted, the amount check would
   never have matched real data — a $250,000 transfer would have evaluated
   `intent.parameters.amount` as INDETERMINATE and fallen through to the
   engine's `NO_DECISION_CONDITION_MATCHED → DENIED` default instead of
   escalating or approving as intended, silently defeating the whole
   threshold. Also confirmed: `intent.amount_minor` is the exact same field
   `_authority_request_params()` (already shipped) sends to CompliIdentity
   as the probe value — so the CompliIdentity call and the decision
   condition are guaranteed to reason about the same number, not two
   independently-populated copies. Fixed to `intent.amount_minor >=
   25000000` (USD $250,000 in minor units, i.e. cents) with an explicit
   `intent.amount_currency == "USD"` guard on both the ESCALATED and
   APPROVED conditions, since the minor-unit multiplier isn't universal
   across currencies (JPY has 0 decimal places, some currencies have 3) —
   without the guard, a non-USD intent could silently reason about the
   wrong scale instead of falling through to the fail-closed default. See
   Sections 2 and 3 above for the corrected conditions.

## Resolved (2026-09-06) — against the live CompliIdentity demo3 acceptance run

The demo3 acceptance run created real principals against a live
CompliIdentity instance and captured 84 request/response pairs
(`demo3_results.json` in the CompliIdentity repo), 13 of them
authority-context calls. Full confirmed reference:
`docs/COMPLIIDENTITY_CONTRACT_VOCABULARY_CONFIRMED.md`.

4. **`credential_expired` removed, `resource_scope_unmatched` added to the
   DENIED list.** `credential_expired` never appears in CompliIdentity's
   real finding vocabulary. `resource_scope_unmatched` was observed firing
   (SENTRY probing `OTHER-CASE-0001` while its delegated grant is scoped to
   `HARBORSTONE-2024-0042`) and is a hard denial. See Section 1.

5. **`authority.reason` is a single derived code, not a raw passthrough.**
   CompliIdentity emits no singular `reason` key — it emits
   `authority_for_request.findings` (a mixed list of positive, informational
   and negative codes; `trust_absent` and `trust_refresh_required` are on
   *every* response) plus the `approval_required` / `limit_exceeded`
   booleans. `authority_context_service._derive_reason` collapses these into
   one code, deny-worthy findings beating `approval_required` so a hard
   denial is never masked into an escalation. The raw list is available as
   `authority.findings` for conditions that need it; the booleans are
   available as `authority.approval_required` etc. This is why the ESCALATED
   condition now also tests the raw boolean (Section 2).

6. **Semantic action + `resource_instance` are sent.** Not a fixed
   `action: "request"`. See Package-level settings above. The HarborStone
   intent construction must supply `compliidentity_action` and
   `compliidentity_resource_instance` per decision step.

7. **CompliIdentity enforces the $250K threshold itself.** Its
   `approval_thresholds` returned `threshold: "24999999"` for
   `aml.action/propose/amount`; propose at 25000000 →
   `approval_required: true`, at 24999999 → `sufficient: true`. The
   package's own amount clause is now redundant with `authority.
   approval_required` on the happy path — kept as the fallback for when the
   authority probe is UNAVAILABLE.

8. **`current_trust_state.fail_closed` is `true` on every response** (the
   continuous-trust loop has not run for any of these fresh principals).
   The decision engine deliberately does **not** gate on it — doing so
   would ESCALATE every HarborStone decision. It is informational only,
   exposed as `authority.current_trust_state` for visibility.

## Still open — needs Claude Code to check against real source

1. Exact `authorized_parameter_constraints` to populate at authorization-
   issuance time for the Hedera-specific transaction (token, amount, memo)
   — separate from this decision-conditions design, but needs to happen at
   the same call site for the demo to bind tightly enough.

## Not addressed here

This document only covers the decision-condition authoring. It does not
cover: the Assessment stage (what makes AML/sanctions screening SATISFIED
vs NOT_SATISFIED in the first place — presumably SENTRY's screening result
feeds this), or the actual package intake/validate/approve/publish
mechanics in CompliAGL, which haven't been exercised yet this session.
