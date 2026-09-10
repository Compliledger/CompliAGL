# Ask: Bootstrap a CompliAGL service principal in CompliIdentity

> **RESOLVED (2026-09-06).** A CompliAGL service principal
> (`compliagl_service`, type `SERVICE`, tenant `harborstone-demo`, role
> `compliagl-authority-reader`) is created as part of the demo setup.
> Confirmed working: acceptance check AC6 issues an authority-context call
> with this principal as `X-Actor-Principal-Id` and gets a `200` identical
> to the platform-admin caller. Auth mechanism confirmed:
> `X-Actor-Principal-Id` header, no bearer token required in the demo
> environment.
>
> **Current principal ID: `ae24b758-edb6-4ffa-895e-78990ca8293c`** — export
> it (with `COMPLIIDENTITY_BASE_URL`) as an environment variable in the
> process that runs the CompliAGL decision engine:
> `COMPLIIDENTITY_SERVICE_PRINCIPAL_ID=ae24b758-edb6-4ffa-895e-78990ca8293c`.
> `authority_context_service.default_client()` reads it via `os.environ`,
> the same way the SecureRob connector reads `SECUREROB_GATEWAY_BASE_URL` —
> it is deliberately **not** a `backend/.env` / pydantic-`Settings` key
> (that model is `extra="forbid"` and does not populate `os.environ`).
>
> This ID is tied to the local **`compliidentity_demo3_step2.db`** working
> instance specifically (created by
> `demo3_step2/compliidentity_setup_phases_1_7.py`). If that instance is
> ever regenerated, CompliIdentity re-issues every principal id and this
> value must be updated again — in the exported environment variable, and in
> `backend/app/db/seed.py` (`_HARBORSTONE_*_PRINCIPAL_ID`, alongside the
> three actor principal ids). The original demo3 acceptance-evidence run
> (CompliIdentity branch `demo3-identity-acceptance-evidence`) issued a
> different id, `0812c9a2-f1c2-4cd2-81a8-8384502ad77e`, now stale.
>
> The rest of this file is kept for historical context.

**Status:** ~~Open item~~ RESOLVED — see note above. Was: non-blocking for
code, blocking for live (non-mock) end-to-end testing of the
CompliIdentity ↔ CompliAGL integration.

## Context

CompliAGL is being wired to call CompliIdentity's real authority-context
endpoint on every decision:

```
POST /api/v1/tenants/{tenant_id}/authority-context/{principal_id}
```

Per `COMPLIAGL_AUTHORITY_CONTRACT.md`, this call requires an
`X-Actor-Principal-Id` header identifying **the caller's own identity** —
i.e. CompliAGL needs to authenticate to CompliIdentity as a principal in its
own right, separate from the human/agent principal (AIRA, SENTRY, Jordan,
etc.) whose authority is being looked up.

As far as we've confirmed from the CompliAGL side, **this service principal
does not exist yet** in CompliIdentity. Claude Code's build is reading it
from an env var (`COMPLIIDENTITY_SERVICE_PRINCIPAL_ID`) and will fail closed
(treat authority as `UNAVAILABLE` → decisions ESCALATE) if it's unset — so
this doesn't block writing or merging code, but it does block the first real
non-mock integration test.

## What we need from you (CompliIdentity owner)

1. **Create a service-principal identity for CompliAGL** in CompliIdentity's
   IAM, with whatever principal type is appropriate for a service-to-service
   caller (not a human, not an agent-delegate — assuming there's a distinct
   category; if not, tell us which existing type to use).
2. **Confirm the authentication mechanism.** The contract doc specifies the
   `X-Actor-Principal-Id` header, but doesn't say (or we haven't found) how
   the caller proves it *is* that principal — is a bearer token / API key
   also required alongside the header, or does something else establish
   trust (mTLS, network-level allowlisting, etc.)?
3. **Tell us what authority this principal itself needs**, if any — does
   CompliAGL's service principal need its own role/permission grant in
   CompliIdentity just to *call* the authority-context endpoint, or is that
   endpoint open to any authenticated service principal regardless of its
   own grants?
4. **Give us the actual principal ID and credential** (or however you
   provision it) once created, so we can set
   `COMPLIIDENTITY_SERVICE_PRINCIPAL_ID` (and any credential env var) for
   integration testing.

## Not in scope for this ask

- This is separate from AIRA's `delegation_rights.allow_agent_recipients`
  flag (needed for the AIRA→SENTRY delegation) — that's a different,
  already-identified Wave 1 setup task on a different principal.
- This doesn't require any changes to the authority-context contract itself
  — the request/response shape is already confirmed and CompliAGL's code is
  being built against it as-is.

## Why this matters now

Everything else in the CompliIdentity↔CompliAGL integration (the code,
the fail-closed logic, the schema/migration) can be built and unit-tested
without this. But we can't run a real end-to-end test — AIRA investigates →
SENTRY screens → CompliAGL calls CompliIdentity → decision reflects real
authority state — until this principal exists. Given it's an IAM
provisioning task rather than a design decision, it seems safe to start in
parallel with the current build rather than waiting.
