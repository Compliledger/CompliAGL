# Demo #3 — Fix Order step 2 (CompliAGL ↔ live CompliIdentity)

Captured evidence + drivers for running CompliAGL's decision engine against a
**real, running CompliIdentity instance** (not the fake/monkeypatched client
the unit tests use).

## Contents

| file | what |
|---|---|
| `compliidentity_setup_phases_1_7.py` | CompliIdentity-side setup driver. A trimmed copy of the CompliIdentity repo's `demo3_setup.py` (commit `37f58b1`): phases 1–6 (bootstrap, permissions, org + principals + agents, roles, bounded AIRA→SENTRY delegation) + phase 7 (read-only acceptance probes). **Stops before phase 8** (the fail-closed teardown) so the instance is left live and clean. |
| `compliidentity_setup_results.json` | Full request/response log from running the above against a fresh `compliidentity_demo3_step2.db`, 2026-09-06. The `ids` block holds the freshly-issued principal ids. |
| `_live_env.py` | Single source of truth for `COMPLIIDENTITY_BASE_URL` / `COMPLIIDENTITY_SERVICE_PRINCIPAL_ID` — the live authority-context wiring `authority_context_service.default_client()` reads from `os.environ`. In-process drivers `import _live_env` (before any `app` import) and the values are applied via `setdefault`, so a real exported env var still wins. |
| `live-env.ps1` | Dot-source (`. .\demo3_step2\live-env.ps1`) to set the same two vars in your own PowerShell session, for interactive REPL / ad-hoc use that isn't one of the self-configuring drivers. |
| `check_live_wiring.py` | Pre-flight: fires one read-only authority-context probe and reports `LIVE` (a real response came back) vs `NOT LIVE` (unconfigured / unreachable / normalized to `UNAVAILABLE`). Exit 0 / 1. Run it before a scenario driver when unsure whether calls are actually reaching CompliIdentity. |

## Running the setup

```
# 1. fresh CompliIdentity instance (separate terminal, CompliIdentity repo)
$env:DATABASE_URL = "sqlite:///./compliidentity_demo3_step2.db"
python -m uvicorn compliidentity.bootstrap:create_app --factory --host 127.0.0.1 --port 8137

# 2. from this repo
backend/venv/Scripts/python.exe demo3_step2/compliidentity_setup_phases_1_7.py
```

## Running the CompliAGL decision scenarios

```
# CompliIdentity from the steps above must still be up on :8137.
backend/venv/Scripts/python.exe demo3_step2/check_live_wiring.py   # optional pre-flight
backend/venv/Scripts/python.exe demo3_step2/compliagl_scenarios.py
```

`compliagl_scenarios.py` self-configures the CompliIdentity env vars via
`import _live_env` — no `.env` and no manual `$env:` needed. For an interactive
session or a script that doesn't do that import:

```
. .\demo3_step2\live-env.ps1
```

The `*.db` files this produces are gitignored — only the driver and the JSON
evidence are tracked, the same treatment as CompliIdentity's
`demo3_setup.py` / `demo3_results.json`.

## Principal-id lifecycle

CompliIdentity issues fresh UUIDs on every instance regeneration. The ids in
`compliidentity_setup_results.json` are what's wired into CompliAGL at
`backend/app/db/seed.py` (`_HARBORSTONE_*_PRINCIPAL_ID`) and — for CompliAGL's
own service principal — `demo3_step2/_live_env.py`
(`COMPLIIDENTITY_SERVICE_PRINCIPAL_ID`) and `demo3_step2/live-env.ps1`.
Regenerate the instance → re-run this driver → update those places with the new
ids. See `backend/ITEM7_ASK_COMPLIIDENTITY_OWNER.md`.
