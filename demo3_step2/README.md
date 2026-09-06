# Demo #3 — Fix Order step 2 (CompliAGL ↔ live CompliIdentity)

Captured evidence + drivers for running CompliAGL's decision engine against a
**real, running CompliIdentity instance** (not the fake/monkeypatched client
the unit tests use).

## Contents

| file | what |
|---|---|
| `compliidentity_setup_phases_1_7.py` | CompliIdentity-side setup driver. A trimmed copy of the CompliIdentity repo's `demo3_setup.py` (commit `37f58b1`): phases 1–6 (bootstrap, permissions, org + principals + agents, roles, bounded AIRA→SENTRY delegation) + phase 7 (read-only acceptance probes). **Stops before phase 8** (the fail-closed teardown) so the instance is left live and clean. |
| `compliidentity_setup_results.json` | Full request/response log from running the above against a fresh `compliidentity_demo3_step2.db`, 2026-09-06. The `ids` block holds the freshly-issued principal ids. |

## Running the setup

```
# 1. fresh CompliIdentity instance (separate terminal, CompliIdentity repo)
$env:DATABASE_URL = "sqlite:///./compliidentity_demo3_step2.db"
python -m uvicorn compliidentity.bootstrap:create_app --factory --host 127.0.0.1 --port 8137

# 2. from this repo
backend/venv/Scripts/python.exe demo3_step2/compliidentity_setup_phases_1_7.py
```

The `*.db` files this produces are gitignored — only the driver and the JSON
evidence are tracked, the same treatment as CompliIdentity's
`demo3_setup.py` / `demo3_results.json`.

## Principal-id lifecycle

CompliIdentity issues fresh UUIDs on every instance regeneration. The ids in
`compliidentity_setup_results.json` are what's wired into CompliAGL at
`backend/app/db/seed.py` (`_HARBORSTONE_*_PRINCIPAL_ID`) and exported as
`COMPLIIDENTITY_SERVICE_PRINCIPAL_ID`. Regenerate the instance → re-run this
driver → update both places with the new ids. See
`backend/ITEM7_ASK_COMPLIIDENTITY_OWNER.md`.
