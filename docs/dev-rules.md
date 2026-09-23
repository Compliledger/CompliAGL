# Development rules — CompliAGL

## Current workstream: Circle Grant MVP (PR 3a)

The plan lives in the Compliledger-MVP repo: `docs/circle-mvp-implementation-plan.md`, PR 3a. CompliAGL is the governed-execution capability; externally, everything is presented as CompliLedger.

## Non-negotiable rules

1. **Use the canonical stack only:** `app/services/canonical/*` and `app/api/v1/*`. `app/mvp2/*` is deprecated; do not extend it.

2. **Do not modify the decision engine.** Leave `decision_service._resolve_outcome`, `_evaluate_conditions` and `authorization_service` issue/verify/consume untouched. New behaviour is expressed as:
   - a governance package (the `app/db/harborstone_package.py` pattern)
   - an evidence connector (the `harborstone_sentry_screening.py` / `securerob.py` pattern)
   - seeds (the `seed_harborstone_*` pattern)

3. **Thin routes.** `POST /api/v1/governed-actions` validates input and calls `governed_action_service.propose`. It contains no logic.

4. **Degraded assurance must DENY, not ESCALATE.** The connector returns a well-formed claim even when assurance is degraded, and a terminal DENIED package condition denies. An unreachable CompliLedger means a missing claim, which must also end in DENIED. Tests prove both.

5. **Fail closed.** Connectors never raise past their boundary. Every failure normalizes to missing or unavailable evidence.

6. **Delegated authority for this MVP** lives in the Treasury Agent's `identity_metadata.delegated_authority`, with `requires_authority_context: false` (decision D5). Do not call CompliIdentity.

7. **Amounts** are USDC minor units (6 decimals): 5 USDC = 5_000_000, and the limit is 10_000_000.

8. **Reuse existing reason codes** where equivalents exist; add new ones only when nothing fits.

## Secrets

Never read `.env`. Configure the CompliLedger base URL and timeout via environment variables, documented in `.env.example`.

## Commands

```
cd backend && pytest -q
cd backend && pytest -q tests/test_circle_*.py
```

Run the tests before reporting a task complete.
