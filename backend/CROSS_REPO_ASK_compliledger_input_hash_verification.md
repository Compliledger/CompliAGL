# Cross-Repo Ask: Does anything recompute CompliAGL's `Decision.input_hash` independently?

**Date:** 2026-09-05
**Raised by:** CompliIdentity authority-context integration work (CompliAGL
repo, `decision_service.py` / `runtime_facts.py` / `authority_context_service.py`)
**Status:** Non-blocking, but needs an answer before the CompliIdentity
authority-context integration can be called fully closed. Same category of
"outside-this-repo fact" as the CompliAGL service-principal bootstrap
question already raised separately with CompliIdentity's owner.
**Addressed to:** whoever owns CompliLedger (and CompliLedger-MVP, if
separate) — this repo cannot answer it from the inside.

---

## What changed in CompliAGL

As part of wiring CompliAGL to call CompliIdentity's authority-context
endpoint, `Decision.input_hash` now folds in a new `authority_hash`
component (alongside the existing `actor_hash`/`intent_hash`/`target_hash`/
`context_hash`). This applies to **every** decision going forward, not just
ones from packages that opt into the CompliIdentity check —
`authority_hash` is simply `null` for packages that don't set
`requires_authority_context: true`, but it's still part of the hashed
payload.

This was flagged internally because a change to what bytes go into a
content hash matters a lot for a proof-chain system, even when the
underlying business logic is unaffected.

## What we ruled out ourselves

We checked CompliAGL's own outbox/event system directly: `decision.created`
is a defined canonical event type in `docs/INTEGRATION_CONTRACTS.md`'s
schema, and the outbox machinery itself (transactional outbox, signing,
retry/dead-letter, per-channel projections) is real and implemented — but
`decision.created` is **never actually published** anywhere in the current
codebase (confirmed by grep: zero call sites construct an `EventContract`
with that event type). So the specific risk of "a live event payload
silently going stale because a consumer expects the old hash shape" does
not exist today, at least not via that path.

## What we can't rule out from CompliAGL's side

`input_hash` is a field on the public `DecisionResponse` API schema — it's
directly reachable by anyone polling CompliAGL's decision endpoints,
regardless of whether any event ever fires. We don't know, and can't find
out from inside CompliAGL's repo:

1. Does CompliLedger (or CompliLedger-MVP, or anything else downstream)
   fetch `Decision.input_hash` via this API and independently recompute it
   to verify a decision hasn't been tampered with?
2. If so, does that verification logic need updating to know about the new
   `authority_hash` component — for **both** newly created decisions and
   any already-persisted decisions from before this change (which will have
   `authority_hash: null` baked in)?
3. Is there anywhere else — a proof bundle, an evidence export, an audit
   report generator — that treats `input_hash` as a fixed, known shape
   rather than an opaque value to compare byte-for-byte against CompliAGL's
   own recomputation?

## What we did on the CompliAGL side in the meantime

We didn't hold the commit for this — decided to ship, since the immediate
risk path was ruled out, but added a comment at the `input_hash`
computation site (`backend/app/services/canonical/decision_service.py`,
just above where `input_hash` is computed in `decide_for_resolution`)
noting exactly which migration introduced `authority_hash`, so if a
mismatch does turn up on your side, there's a clear pointer to why.

## Why this is worth resolving before calling the integration "done"

If CompliLedger does recompute this hash and doesn't know about the new
field yet, verification could silently start failing (or silently start
succeeding on a wrong basis, which is worse) the next time someone touches
that code — and it might not surface until an actual audit/proof-check
happens, at a much less convenient time than now.

---

## Update (2026-09-06): human-approval orchestration adds more to the same payload

**Same question, same category, no new mitigation needed on our side beyond
this note.** The human-approval orchestration work changes `input_hash`
shape two more times:

1. **New `approval_hash` key** (migration 0017). `null` on every decision
   that isn't a re-decision consuming an escalation approval — but, like
   `authority_hash`, it is part of the hashed payload for *all* decisions
   from this point on.
2. **`authority_hash` now hashes over more.**
   `runtime_facts.build_authority_facts` gained an `applicable_approvals`
   entry (CompliIdentity's declaration of which approver type an escalated
   action requires). So `authority_hash` — and therefore `input_hash` /
   `decision_hash` — differs for authority-gated decisions from here on
   *even at byte-identical inputs* relative to decisions computed before
   this change.

We re-checked the same things: no in-repo recompute of a persisted
`Decision.input_hash`, and `IntegrationEventType.DECISION_CREATED` still has
zero live publishers. The open questions above (does CompliLedger recompute
`input_hash` from the public API? does any proof-bundle / evidence-export /
audit-report generator treat its shape as fixed?) now apply to
`approval_hash` and the widened `authority_hash` as well as the original
`authority_hash` addition.
