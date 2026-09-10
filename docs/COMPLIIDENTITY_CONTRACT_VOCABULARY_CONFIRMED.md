# CompliIdentity authority-context — confirmed contract vocabulary

**Status:** Confirmed reference material, not an open ask. Captured
2026-09-06 from CompliIdentity's `demo3` acceptance run — real principals
created against a live local CompliIdentity instance, 84 request/response
pairs recorded in `demo3_results.json` (CompliIdentity repo,
branch `demo3-identity-acceptance-evidence`), 13 of them authority-context
calls covering the full range of outcomes.

This documents what the endpoint **actually returns**, for whoever authors
the next governance package that sets `requires_authority_context: true`.
CompliAGL's parsing (`app/services/canonical/authority_context_service.py`)
and the HarborStone package (`app/db/harborstone_package.py`) are already
aligned to this.

## Endpoint

```
POST /api/v1/tenants/{tenant_id}/authority-context/{principal_id}
```

- `tenant_id` **equals CompliAGL's `organization_id`** — confirmed: every
  response echoed `"tenant_id": "harborstone-demo"` for the `harborstone-demo`
  org.
- Headers CompliIdentity requires: `X-Tenant-Id` and `X-Actor-Principal-Id`
  (the *caller's* own principal — CompliAGL's service principal, distinct
  from the `{principal_id}` in the path being asked about). The demo used no
  bearer token. CompliAGL's client sends both headers exactly as expected.
- Request body used in the acceptance run:
  `{"resource": ..., "action": ..., "resource_instance": ..., "attribute": ..., "value": ...}`
  — `attribute`/`value` only for amount-bearing probes.
- **`contract_version` in the request body: unverified.** CompliAGL's client
  sends `"contract_version": "1"`; the demo script never sent it and got
  `200`. The response always echoes `"contract_version": "1"`. It is most
  likely ignored as an unknown field, but CompliIdentity has not confirmed
  it either accepts or rejects the extra key. Harmless in practice; flagged
  for completeness.

## `resource` / `action` vocabulary (as exercised)

| resource | actions seen |
|---|---|
| `aml.case` | `read`, `assess` |
| `aml.action` | `propose`, `approve` |
| `sanctions.screening` | `read` |
| `aml.escalation` | `create` |

`action` is the **real semantic verb**, not a generic `"request"` probe.
`resource_instance` (e.g. `"HARBORSTONE-2024-0042"`) scopes the check to a
specific case — this is what makes CompliIdentity's per-case grant scoping
(a grant scoped to one case, inherited by a delegate) visible to the probe.

## `authority_for_request` — the block CompliAGL reasons about

```json
{
  "sufficient": true,
  "permission_present": true,
  "limit_exceeded": false,
  "approval_required": false,
  "findings": ["permission_present", "trust_absent", "trust_refresh_required"],
  "matching_permissions": [ ... ],
  "applicable_limits": [],
  "applicable_approvals": []
}
```

- **There is no singular `reason` key.** An earlier CompliAGL draft read
  `authority_for_request.reason` — it does not exist, so `authority.reason`
  was `None` on every real call.
- `sufficient` is the master allow/deny boolean.
- `approval_required` and `limit_exceeded` are **explicit booleans**, not
  only findings.
- `findings` is a **mixed list** — positive, informational, and negative
  codes together. It is **not** a list of denial reasons.

### `findings` vocabulary (complete, as observed across all 13 calls)

| finding | meaning | class |
|---|---|---|
| `permission_present` | a matching permission was found | positive |
| `trust_absent` | no continuous-trust decision exists for this principal | informational — **on every response** |
| `trust_refresh_required` | trust state needs a refresh | informational — **on every response** |
| `approval_required` | human approval needed (also the boolean) | escalation |
| `permission_missing` | no matching permission (out-of-scope, cascade-revoked, or delegation-revoked) | hard denial |
| `delegation_revoked` | the delegation was explicitly revoked (co-occurs with `permission_missing`) | hard denial |
| `principal_not_active` | the principal is disabled (also top-level `"active": false`) | hard denial |
| `resource_scope_unmatched` | permission present but `resource_instance` not in the grant's scope | hard denial |

`trust_absent` / `trust_refresh_required` appear on **every** response
because the continuous-trust loop has not run for any of these fresh
principals — do not treat their presence as a denial signal.

**Not observed / do not exist in the model:**
- `credential_expired` — was in an early draft's DENIED list; removed.
- `limit_exceeded` as a *finding* — it is a boolean only (was `false` in
  every captured call).

### How CompliAGL collapses this into `authority.reason`

`authority_context_service._derive_reason()` produces a single code for
package conditions authored against `authority.reason`:

1. First match, in priority order:
   `principal_not_active` → `delegation_revoked` → `resource_scope_unmatched`
   → `permission_missing` (all DENIED-worthy).
2. Else `limit_exceeded` boolean → `"limit_exceeded"`.
3. Else `approval_required` boolean / finding → `"approval_required"`.
4. Else `None`.

Deny-worthy findings are always checked before `approval_required`, so a
hard denial is never masked into an escalation. The raw list stays on
`authority.findings`; the booleans stay on `authority.permission_present` /
`authority.approval_required` / `authority.limit_exceeded` for conditions
that want the unreduced signals.

## `current_trust_state` — an object, not a string

```json
{
  "present": false,
  "fail_closed": true,
  "stale": false,
  "refresh_required": true,
  "decision_id": null,
  "outcome": null,
  "valid_until": null,
  "policy_id": null,
  "policy_version": null,
  "reason_codes": ["trust_state_absent"]
}
```

`fail_closed: true` on **every** captured response (no trust loop has run).
CompliAGL exposes it as `authority.current_trust_state` for visibility but
the decision engine **deliberately does not gate on it** — gating would
ESCALATE every decision for these principals. Informational only.

## Approval thresholds — CompliIdentity enforces amount limits itself

For AIRA's `aml.action / propose` permission, the response carried:

```json
"approval_thresholds": [
  {"resource": "aml.action", "action": "propose", "attribute": "amount",
   "threshold": "24999999", "approver_principal_type": "HUMAN"}
]
```

Confirmed behaviour: `propose` with `value: "25000000"` →
`approval_required: true`; with `value: "24999999"` → `sufficient: true`.
A package's own amount threshold is therefore redundant with
`authority.approval_required` on the happy path — keep it only as the
fallback for when the authority probe is `UNAVAILABLE`.

## Proof / integrity

- `proof_ref` is `null` on **every** real response.
- The real signed anchor is the `integrity` block:
  `{"content_hash": <hex>, "signature": <hex>, "signature_algorithm":
  "ed25519", "signer_key_id": "compliidentity.proof.ed25519.dev"}`.
- CompliAGL captures `integrity.content_hash` as
  `AuthorityContext.integrity_content_hash` and folds it into the decision's
  `authority_hash`.
- `authority_revision` is a stable content-revision fingerprint (same value
  across two calls for the same principal/grants), not a timestamp.

## Top-level fields CompliAGL does *not* use (and why that's fine)

`authorizes` / `executes` / `agl_decision` were `false` / `false` /
`"not_made"` on **every** response, including fully-authorized ones — they
concern whether an AGL decision has been recorded back to CompliIdentity,
not whether the principal may act. `authority_for_request.sufficient` is the
correct field for "may this principal act". Also unused: `permissions`,
`resource_scope`, `roles`, `assurance`, `policy_refs`, `delegation_chain`,
`evidence`, `principal` — available in `AuthorityContext.raw` if ever
needed.
