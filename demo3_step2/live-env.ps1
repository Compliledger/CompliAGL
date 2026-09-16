# Dot-source this before running an interactive REPL / ad-hoc script that
# exercises CompliAGL's decision engine against the live CompliIdentity
# instance:
#
#     . .\demo3_step2\live-env.ps1
#
# The in-process scenario drivers (compliagl_scenarios.py, ...) do NOT need
# this -- they import demo3_step2/_live_env.py, which is the single source of
# truth for these two values. Keep this file and _live_env.py in sync.
#
# These are deliberately os.environ-only, not backend/.env / pydantic Settings
# keys. See backend/ITEM7_ASK_COMPLIIDENTITY_OWNER.md.

$env:COMPLIIDENTITY_BASE_URL = "http://127.0.0.1:8137"
# "CompliAGL Service" SERVICE principal in the live instance (refreshed
# 2026-09-16 against a freshly-regenerated compliidentity_demo3_step2_live.db).
$env:COMPLIIDENTITY_SERVICE_PRINCIPAL_ID = "6e7cf703-d5ab-4df1-bad4-52b7c5213e28"

Write-Host "CompliIdentity live env set:"
Write-Host "  COMPLIIDENTITY_BASE_URL              = $env:COMPLIIDENTITY_BASE_URL"
Write-Host "  COMPLIIDENTITY_SERVICE_PRINCIPAL_ID  = $env:COMPLIIDENTITY_SERVICE_PRINCIPAL_ID"
