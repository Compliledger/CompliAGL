"""CompliLedger Demo #3 -- Fix Order step 2: CompliIdentity setup (phases 1-7 ONLY).

This is a trimmed copy of the CompliIdentity repo's ``demo3_setup.py`` (commit
37f58b1, branch demo3-identity-acceptance-evidence). It replicates phases 1-6
(bootstrap, admin role, domain permissions, org + principals + agents, roles /
bindings / assignments, the bounded AIRA->SENTRY delegation) and phase 7
(read-only acceptance probes).

It deliberately STOPS before phase 8 (the fail-closed teardown that disables
AIRA/SENTRY and revokes the delegation), because CompliAGL's step-2 acceptance
scenarios need a clean, live state:

    * AIRA active, with aml.case:read / aml.case:assess / sanctions.screening:read
      / aml.escalation:create, and aml.action:propose bounded by an approval
      threshold at $250,000.00; assignment scoped to case HARBORSTONE-2024-0042
      with delegation rights.
    * SENTRY active, NO role -- authority is delegation-only.
    * The AIRA->SENTRY delegation ACTIVE: actions ["read"], selector
      "sanctions.screening", max_depth 0, scoped (inherited) to the one case.
    * Jordan Lee active, with aml.action:approve, scoped to the case.
    * A CompliAGL Service (SERVICE) principal for the authority-context caller.

Run against a FRESH CompliIdentity instance (empty DB, bootstrap window open):

    cd C:\\Users\\Acer\\Desktop\\CompliIdentity-repo
    $env:DATABASE_URL = "sqlite:///./compliidentity_demo3_step2.db"
    python -m uvicorn compliidentity.bootstrap:create_app --factory --host 127.0.0.1 --port 8137

    # then, from the CompliAGL repo:
    python demo3_step2\\compliidentity_setup_phases_1_7.py

The freshly-issued principal IDs are printed at the end and written to
``demo3_step2/compliidentity_setup_results.json`` (full request/response log).
Those IDs -- not the ones from the earlier demo3 run -- are what get seeded into
CompliAGL's ActorIdentity records.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx

BASE = os.environ.get("COMPLIIDENTITY_BASE_URL", "http://127.0.0.1:8137")
TENANT = "harborstone-demo"
CASE = "HARBORSTONE-2024-0042"
THRESHOLD = "24999999"  # strict > ; == >= 25_000_000 (one $250,000.00 boundary)

_RESULTS_PATH = os.path.join(os.path.dirname(__file__), "compliidentity_setup_results.json")

client = httpx.Client(base_url=BASE, timeout=30.0)
LOG: list[dict] = []
IDS: dict[str, str] = {}


def call(method: str, path: str, *, actor: str | None = None, json_body: dict | None = None,
         expect: int | tuple[int, ...] = (200, 201), label: str = "") -> httpx.Response:
    headers = {"X-Tenant-Id": TENANT}
    if actor:
        headers["X-Actor-Principal-Id"] = actor
    resp = client.request(method, path, headers=headers, json=json_body)
    ok_set = (expect,) if isinstance(expect, int) else expect
    entry = {
        "label": label or f"{method} {path}",
        "method": method, "path": path, "actor": actor,
        "request_body": json_body, "status": resp.status_code,
    }
    try:
        entry["response"] = resp.json()
    except Exception:
        entry["response"] = resp.text
    LOG.append(entry)
    if resp.status_code not in ok_set:
        print(f"\n!!! UNEXPECTED {resp.status_code} on [{entry['label']}] (wanted {ok_set})")
        print(json.dumps(entry, indent=2, default=str))
        _dump()
        sys.exit(1)
    return resp


def _dump() -> None:
    out = {"ids": IDS, "log": LOG}
    with open(_RESULTS_PATH, "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(f"\n--- results written: {_RESULTS_PATH} ---")


def section(t: str) -> None:
    print(f"\n{'='*70}\n{t}\n{'='*70}")


# ------------------------------------------------------------------ Phase 1: bootstrap
section("PHASE 1  bootstrap principals")
IDS["bootstrap_op"] = call("POST", "/api/v1/principals",
    json_body={"principal_type": "HUMAN", "display_name": "Bootstrap Operator"},
    label="create Bootstrap Operator (no actor, bootstrap window)").json()["principal_id"]
IDS["platform_admin"] = call("POST", "/api/v1/principals", actor=IDS["bootstrap_op"],
    json_body={"principal_type": "HUMAN", "display_name": "Platform Admin"},
    label="create Platform Admin").json()["principal_id"]
print("bootstrap_op   =", IDS["bootstrap_op"])
print("platform_admin =", IDS["platform_admin"])

# ------------------------------------------------------------------ Phase 2: admin role, close bootstrap
section("PHASE 2  admin system role -> close bootstrap window")
ADMIN_PERMS = [
    ("iam.principal", "create"), ("iam.principal", "read"),
    ("iam.principal", "update"), ("iam.principal", "deactivate"),
    ("iam.agent", "create"), ("iam.agent", "read"), ("iam.agent", "deactivate"),
    ("iam.permission", "create"), ("iam.permission", "read"),
    ("iam.role", "create"), ("iam.role", "read"), ("iam.role", "update"),
    ("iam.role", "deactivate"), ("iam.role", "assign"),
    ("iam.assignment", "assign"), ("iam.assignment", "revoke"), ("iam.assignment", "read"),
    ("iam.authorize", "decide"),
]
perm_ids: dict[tuple[str, str], str] = {}
for res, act in ADMIN_PERMS:
    pid = call("POST", "/api/v1/permissions", actor=IDS["bootstrap_op"],
        json_body={"resource": res, "action": act, "description": f"admin {res}:{act}"},
        label=f"perm {res}:{act}").json()["permission_id"]
    perm_ids[(res, act)] = pid

admin_role = call("POST", "/api/v1/roles", actor=IDS["bootstrap_op"],
    json_body={"name": "harborstone-platform-admin", "system_role": True,
               "description": "Demo #3 tenant admin / break-glass"},
    label="role harborstone-platform-admin").json()["role_id"]
IDS["admin_role"] = admin_role
for (res, act), pid in perm_ids.items():
    call("POST", f"/api/v1/roles/{admin_role}/permissions", actor=IDS["bootstrap_op"],
        json_body={"permission_id": pid}, label=f"bind {res}:{act} -> admin role")

adm_assign = call("POST", f"/api/v1/principals/{IDS['platform_admin']}/roles", actor=IDS["bootstrap_op"],
    json_body={"role_id": admin_role, "assignment_reason": "Demo #3 bootstrap platform admin"},
    label="assign admin role -> Platform Admin (closes bootstrap)").json()
IDS["admin_assignment"] = adm_assign["assignment_id"]
ADM = IDS["platform_admin"]

# confirm bootstrap closed: an unauth principals write must now 401
probe = client.request("POST", "/api/v1/roles", headers={"X-Tenant-Id": TENANT},
                       json={"name": "should-fail"})
LOG.append({"label": "bootstrap-closed probe (POST /roles no actor -> expect 401)",
            "status": probe.status_code, "response": probe.json()})
print("bootstrap-closed probe status:", probe.status_code, "(expect 401)")
assert probe.status_code == 401, "bootstrap did NOT close"

# ------------------------------------------------------------------ Phase 3: domain permissions
section("PHASE 3  domain permissions")
DOMAIN_PERMS = [
    ("aml.case", "read"), ("aml.case", "assess"),
    ("sanctions.screening", "read"),
    ("aml.action", "propose"), ("aml.action", "approve"),
    ("aml.escalation", "create"),
]
for res, act in DOMAIN_PERMS:
    pid = call("POST", "/api/v1/permissions", actor=ADM,
        json_body={"resource": res, "action": act, "description": f"HarborStone {res}:{act}"},
        label=f"domain perm {res}:{act}").json()["permission_id"]
    perm_ids[(res, act)] = pid
# reuse iam.assignment:read for compliagl-service (already created in Phase 2)

# ------------------------------------------------------------------ Phase 4: org + principals
section("PHASE 4  organization + principals + agents")
IDS["harborstone_org"] = call("POST", "/api/v1/principals", actor=ADM,
    json_body={"principal_type": "ORGANIZATION", "display_name": "HarborStone AML Platform"},
    label="create org HarborStone AML Platform").json()["principal_id"]
IDS["jordan"] = call("POST", "/api/v1/principals", actor=ADM,
    json_body={"principal_type": "HUMAN", "display_name": "Jordan Lee"},
    label="create Jordan Lee (HUMAN approver)").json()["principal_id"]

ORG = IDS["harborstone_org"]
aira = call("POST", "/api/v1/agents", actor=ADM, json_body={
    "agent_name": "AIRA", "agent_type": "ANALYST",
    "owner_principal_id": ORG, "organization_principal_id": ORG,
    "deployment_environment": "dev",
    "creation_reason": "HarborStone Demo #3 AML investigator",
    "creation_source": "demo3-setup",
}, label="create AIRA (AI_AGENT / ANALYST)").json()
IDS["aira"] = aira["principal_id"]
sentry = call("POST", "/api/v1/agents", actor=ADM, json_body={
    "agent_name": "SENTRY", "agent_type": "TOOL",
    "owner_principal_id": ORG, "organization_principal_id": ORG,
    "deployment_environment": "dev",
    "creation_reason": "HarborStone Demo #3 sanctions screening (delegated only)",
    "creation_source": "demo3-setup",
}, label="create SENTRY (AI_AGENT / TOOL)").json()
IDS["sentry"] = sentry["principal_id"]
IDS["compliagl_service"] = call("POST", "/api/v1/principals", actor=ADM,
    json_body={"principal_type": "SERVICE", "display_name": "CompliAGL Service"},
    label="create CompliAGL Service (SERVICE / ITEM7)").json()["principal_id"]
for k in ("harborstone_org", "jordan", "aira", "sentry", "compliagl_service"):
    print(f"{k:18s} = {IDS[k]}")

# ------------------------------------------------------------------ Phase 5: roles / bindings / assignments
section("PHASE 5  domain roles, bindings, assignments")
# AIRA
aira_role = call("POST", "/api/v1/roles", actor=ADM,
    json_body={"name": "aira-aml-investigator", "description": "Demo #3 AIRA authority"},
    label="role aira-aml-investigator").json()["role_id"]
IDS["aira_role"] = aira_role
for res, act in [("aml.case", "read"), ("aml.case", "assess"),
                 ("sanctions.screening", "read"), ("aml.escalation", "create")]:
    call("POST", f"/api/v1/roles/{aira_role}/permissions", actor=ADM,
        json_body={"permission_id": perm_ids[(res, act)]},
        label=f"bind {res}:{act} -> aira role")
call("POST", f"/api/v1/roles/{aira_role}/permissions", actor=ADM, json_body={
    "permission_id": perm_ids[("aml.action", "propose")],
    "constraints": {"approvals": [{
        "resource": "aml.action", "action": "propose", "attribute": "amount",
        "threshold": THRESHOLD, "approver_principal_type": "HUMAN"}]},
}, label="bind aml.action:propose -> aira role (approval threshold)")
aira_assign = call("POST", f"/api/v1/principals/{IDS['aira']}/roles", actor=ADM, json_body={
    "role_id": aira_role, "assignment_reason": "HarborStone Demo #3 AIRA",
    "constraints": {
        "delegation": {"may_delegate": True, "max_depth": 1, "allow_agent_recipients": True},
        "resource_scope": [CASE],
    },
}, label="assign aira role -> AIRA (delegation rights + case scope)").json()
IDS["aira_assignment"] = aira_assign["assignment_id"]

# Jordan
jordan_role = call("POST", "/api/v1/roles", actor=ADM,
    json_body={"name": "jordan-aml-approver", "description": "Demo #3 Jordan HITL approver"},
    label="role jordan-aml-approver").json()["role_id"]
IDS["jordan_role"] = jordan_role
call("POST", f"/api/v1/roles/{jordan_role}/permissions", actor=ADM,
    json_body={"permission_id": perm_ids[("aml.action", "approve")]},
    label="bind aml.action:approve -> jordan role")
jordan_assign = call("POST", f"/api/v1/principals/{IDS['jordan']}/roles", actor=ADM, json_body={
    "role_id": jordan_role, "assignment_reason": "HarborStone HITL approver",
    "constraints": {"resource_scope": [CASE]},
}, label="assign jordan role -> Jordan Lee (case scope)").json()
IDS["jordan_assignment"] = jordan_assign["assignment_id"]

# CompliAGL service
agl_role = call("POST", "/api/v1/roles", actor=ADM,
    json_body={"name": "compliagl-authority-reader", "description": "ITEM7 authority-context caller"},
    label="role compliagl-authority-reader").json()["role_id"]
IDS["agl_role"] = agl_role
call("POST", f"/api/v1/roles/{agl_role}/permissions", actor=ADM,
    json_body={"permission_id": perm_ids[("iam.assignment", "read")]},
    label="bind iam.assignment:read -> agl role")
agl_assign = call("POST", f"/api/v1/principals/{IDS['compliagl_service']}/roles", actor=ADM, json_body={
    "role_id": agl_role, "assignment_reason": "ITEM7: CompliAGL authority-context caller"},
    label="assign agl role -> CompliAGL Service").json()
IDS["agl_assignment"] = agl_assign["assignment_id"]
print("SENTRY: no role assignment (authority is delegation-only)")

# ------------------------------------------------------------------ Phase 6: delegation AIRA -> SENTRY
section("PHASE 6  bounded delegation  AIRA -> SENTRY  (actor = AIRA)")
now = datetime.now(timezone.utc).replace(microsecond=0)
deleg = call("POST", "/api/v1/delegations", actor=IDS["aira"], json_body={
    "delegate_principal_id": IDS["sentry"],
    "actions": ["read"],
    "resource_selector": "sanctions.screening",
    "purpose": f"HarborStone AML case {CASE}: SENTRY performs delegated sanctions screening only",
    "valid_from": now.isoformat(),
    "valid_until": (now + timedelta(hours=24)).isoformat(),
    "max_depth": 0,
    "revocable": True,
}, label="create delegation AIRA->SENTRY").json()
IDS["delegation"] = deleg["delegation_id"]
print("delegation_id =", IDS["delegation"])
print("  status                :", deleg["status"])
print("  resource_selector     :", deleg["resource_selector"])
print("  actions               :", deleg["actions"])
print("  delegated_permissions :", deleg["delegated_permissions"])
print("  resource_scopes       :", deleg["resource_scopes"])
print("  max_depth             :", deleg["max_depth"])
print("  allow_agent_recipients:", deleg["allow_agent_recipients"])

# ------------------------------------------------------------------ Phase 7: acceptance probes
section("PHASE 7  acceptance / verification probes")


def ac(principal: str, body: dict, actor: str, label: str) -> dict:
    r = call("POST", f"/api/v1/tenants/{TENANT}/authority-context/{principal}",
             actor=actor, json_body=body, label=label, expect=(200,))
    d = r.json()
    afr = d.get("authority_for_request", {})
    print(f"\n[{label}]  HTTP {r.status_code}")
    print(f"   active={d.get('active')}  sufficient={afr.get('sufficient')}  "
          f"permission_present={afr.get('permission_present')}  "
          f"approval_required={afr.get('approval_required')}  limit_exceeded={afr.get('limit_exceeded')}")
    print(f"   findings={afr.get('findings')}")
    print(f"   delegation_chain={d.get('delegation_chain')}")
    return d


ac(IDS["aira"], {"resource": "aml.case", "action": "read", "resource_instance": CASE},
   ADM, "AC1  AIRA authority query (aml.case:read, in-scope)")
ac(IDS["aira"], {"resource": "aml.action", "action": "propose", "attribute": "amount",
                 "value": "25000000", "resource_instance": CASE},
   ADM, "AIRA propose amount=25000000 (== $250,000.00) -> expect approval_required")
ac(IDS["aira"], {"resource": "aml.action", "action": "propose", "attribute": "amount",
                 "value": "24999999", "resource_instance": CASE},
   ADM, "AIRA propose amount=24999999 (< $250,000.00) -> expect sufficient")
ac(IDS["sentry"], {"resource": "sanctions.screening", "action": "read", "resource_instance": CASE},
   ADM, "AC2  SENTRY authority query (sanctions.screening:read, delegated, in-scope)")
ac(IDS["jordan"], {"resource": "aml.action", "action": "approve", "resource_instance": CASE},
   ADM, "AC3  Jordan approval-authority query (aml.action:approve)")
dg = call("GET", f"/api/v1/delegations/{IDS['delegation']}", actor=ADM,
          label="AC4  delegation record", expect=(200,)).json()
print(f"\n[AC4  delegation]  status={dg['status']}  allow_agent_recipients={dg['allow_agent_recipients']}  "
      f"resource_selector={dg['resource_selector']}  max_depth={dg['max_depth']}")
ac(IDS["sentry"], {"resource": "aml.case", "action": "read", "resource_instance": CASE},
   ADM, "AC5  SENTRY aml.case:read OUTSIDE delegated scope -> expect insufficient/permission_missing")
ac(IDS["sentry"], {"resource": "sanctions.screening", "action": "read", "resource_instance": "OTHER-CASE-0001"},
   ADM, "bonus  SENTRY sanctions.screening:read on OTHER-CASE-0001 -> expect resource_scope_unmatched")
ac(IDS["aira"], {"resource": "aml.case", "action": "read", "resource_instance": CASE},
   IDS["compliagl_service"], "AC6  authority-context as CompliAGL Service principal (ITEM7)")

# ------------------------------------------------------------------ done (NO phase 8 teardown)
section("IDS  (fresh -- seed THESE into CompliAGL, not the earlier demo3 run's ids)")
for k, v in IDS.items():
    print(f"{k:20s} = {v}")
print("\nPRINCIPAL IDS for CompliAGL ActorIdentity seeding:")
print(json.dumps({
    "tenant__organization_id": TENANT,
    "case_resource_instance": CASE,
    "aira": IDS["aira"],
    "sentry": IDS["sentry"],
    "jordan": IDS["jordan"],
    "harborstone_org": IDS["harborstone_org"],
    "compliagl_service": IDS["compliagl_service"],
    "delegation": IDS["delegation"],
}, indent=2))
_dump()
print("\nDONE -- state is LIVE and CLEAN (no teardown). Ready for CompliAGL scenarios.")
