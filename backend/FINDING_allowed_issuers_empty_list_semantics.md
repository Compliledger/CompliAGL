# Empirical finding: `allowed_issuers: []` means "no restriction," not "reject everything"

**Date:** 2026-08-17
**Method:** live test, not code-reading alone. Registered a new trial package
version (`0.0.8-trial-localdev-allowed-issuers-test`, package id
`b60dc69b-63e2-4bb4-bc2b-8e068f94feb4`) identical in every field to the
currently-published `0.0.7-trial-localdev` (id
`6d7c132b-6dcc-49f1-923a-01e260bdc974`) except
`EV-SECUREROB-PERCEPTION.allowed_issuers`: `[]` -> `["compliagl-execution-gateway"]`.
Ran two fresh live requests end-to-end through the real Gateway (`:8080`) ->
CompliAGL (`:8000`) pipeline, back-to-back, same servers, same safe-scenario
perception facts, distinct `correlation_id`s. Script:
`CompliAGL-Execution-Gateway/trial_test_allowed_issuers.py`; full request/
response log: `CompliAGL-Execution-Gateway/trial_allowed_issuers_result.md`.

Policy resolution correctly picked up each package version by its normal
highest-published-version selection rule
(`policy_resolution_service._resolution_sort_key`) — confirmed via
`GET /api/v1/policy-resolutions/{id}`:

| Run | Package version resolved | `allowed_issuers` |
|---|---|---|
| A | `0.0.7-trial-localdev` | `[]` |
| B | `0.0.8-trial-localdev-allowed-issuers-test` | `["compliagl-execution-gateway"]` |

## The direct answer

Empty `allowed_issuers` means **no restriction** — it falls through to
`connector_trusted_issuers`, not "reject everything." Confirmed by directly
inspecting the persisted `EvidenceValidationResult.checks` for real,
Gateway-collected evidence (not synthetic data) on both runs:

```
Run A (allowed_issuers=[]):
  raw.issuer = "compliagl-execution-gateway"
  checks.issuer_trust = True

Run B (allowed_issuers=["compliagl-execution-gateway"]):
  raw.issuer = "compliagl-execution-gateway"
  checks.issuer_trust = True
```

Identical. This is exactly what `evidence_validation_service.evaluate()`
(lines 111-116) predicts by reading the code:

```python
if allowed_issuers:
    issuer_trust = raw.issuer in allowed_issuers
elif trusted_issuers:                      # <- empty-list case lands here
    issuer_trust = raw.issuer in trusted_issuers
else:
    issuer_trust = True
```

`trusted_issuers` here is `provenance["connector_trusted_issuers"]`, which
for the SecureRob connector is always `("compliagl-execution-gateway",)`
(`connectors/securerob.py:80`) — so with an empty `allowed_issuers`, the
check silently falls back to the connector's own trusted-issuer list rather
than rejecting on an empty allow-list. If the code instead meant "reject
everything when the list is empty," Run A's `issuer_trust` would have come
back `False` and the outcome would have been `UNTRUSTED_SOURCE` /
`EVIDENCE_ISSUER_UNTRUSTED` — it didn't.

## Why the *top-level decision outcome* looks identical too (and why that's a red herring)

Both runs' first attempt actually came back `collection_status: NOT_FOUND`
(a separate, already-documented Gateway-side capture-vs-queryable-availability
race — not part of this test). Retrying `POST /evidence-collections` for
each `policy_resolution_id` a few seconds later got real `COLLECTED`
evidence for both. At that point:

| Run | `checks.target_binding` | Validation outcome | Decision outcome | Decision reason codes |
|---|---|---|---|---|
| A | `False` | `TARGET_MISMATCH` | `DENIED` | `MANDATORY_CONTROL_FAILED`, `POLICY_OK` |
| B | `False` | `TARGET_MISMATCH` | `DENIED` | `MANDATORY_CONTROL_FAILED`, `POLICY_OK` |

Both runs hit `TARGET_MISMATCH` — the identifier-mismatch bug already
written up in `PENDING_REVIEW_target_binding_identifier_mismatch.md`
(`Target.id` vs `Target.external_identifier`), which is still unfixed and
fires unconditionally regardless of `allowed_issuers`. Since
`evidence_validation_service._decide()` checks `issuer_trust`
(`UNTRUSTED_SOURCE`) *before* `target_binding` (`TARGET_MISMATCH`) in its
precedence order, a difference in `allowed_issuers` *would* have been
visible at the top-level outcome if it had mattered — it would have shown up
as `UNTRUSTED_SOURCE` before ever reaching the target-binding check. It
didn't, because `issuer_trust` was `True` in both runs. The `TARGET_MISMATCH`
seen in both is a separate, already-known, unrelated bug — not something
this test's `allowed_issuers` change caused or could have masked from a
"reject everything" hypothesis; if that hypothesis had been true, Run A
would have failed one precedence step earlier than Run B, not at the same
step.

## Conclusion

`allowed_issuers: []` is safe/intentional "no restriction, defer to the
connector's own trusted-issuer list" — not a footgun that silently rejects
all evidence. No code change is indicated by this finding.

---

## Final outcome (2026-08-17, later same night): pipeline reached real APPROVED

Both runs documented above ended in `DENIED`/`MANDATORY_CONTROL_FAILED` due to
the target-binding identifier mismatch (see
`PENDING_REVIEW_target_binding_identifier_mismatch.md`), which was still
unfixed at the time this document was written. That mismatch has since been
fixed (CompliAGL backend commit `c362b89`), and a separate, previously
undiscovered bug was found and fixed the same night in the Gateway repo
(`CompliAGL-Execution-Gateway`): the draft SecureRob governance package's
`control_definitions[].evaluation_expression` fields were written against a
`context.operational_state_snapshot.*` namespace that
`control_evaluation_service._evidence_facts()` never binds — only
`evidence[...][claims][...]` is bound for that code path. Fixed in Gateway
commits `d0fe2d2` (expression fix) and `e8f779c` (doc/prose correction
distinguishing `control_definitions[].evaluation_expression`'s binding from
`decision_conditions[].expression`'s).

With both fixes in place, a live end-to-end run
(`CompliAGL-Execution-Gateway/trial_final_combined_fix_v2_result.md`) reached
a genuine `outcome: "APPROVED"` / `reason_codes: ["DECISION_APPROVED",
"APPROVED_BY_POLICY"]` — not a replay, not a cached/stale result. The
`allowed_issuers` question this document investigates was already correctly
ruled out as a factor before this final fix, and remains correctly ruled out:
it played no role in either the `DENIED` result documented above or the
`APPROVED` result that followed the target-binding and expression-namespace
fixes.
