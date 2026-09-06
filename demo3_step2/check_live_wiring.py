"""Is CompliAGL actually wired to a LIVE CompliIdentity right now?

A fast pre-flight for the demo3 drivers. Answers one question: if the decision
engine made an authority-context call this second, would it reach a real
CompliIdentity instance -- or silently fall back to UNAVAILABLE (fail closed,
every gated decision ESCALATES)?

    backend/venv/Scripts/python.exe demo3_step2/check_live_wiring.py

Exit code 0 == LIVE (a real authority-context response came back).
Exit code 1 == NOT live (client unconfigured, unreachable, or the probe
normalized to UNAVAILABLE). Nothing here mutates state -- the probe is a
read-only authority-context lookup for AIRA's own valid grant.
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# Single source of truth for COMPLIIDENTITY_BASE_URL /
# COMPLIIDENTITY_SERVICE_PRINCIPAL_ID -- applied via setdefault, a real
# exported env var still wins. MUST precede the app import below.
import _live_env  # noqa: E402,F401

from app.db.seed import (  # noqa: E402
    HARBORSTONE_ORG_ID,
    _HARBORSTONE_AIRA_PRINCIPAL_ID,
)
from app.services.canonical import authority_context_service  # noqa: E402

# AIRA's own valid grant -- proposing on the HarborStone case she's scoped to.
# No `value`, so a healthy instance returns permission_present=true with no
# limit/approval flags: an unambiguous "the wiring works" signal.
_PROBE = dict(
    organization_id=HARBORSTONE_ORG_ID,
    principal_id=_HARBORSTONE_AIRA_PRINCIPAL_ID,
    resource="aml.action",
    action="propose",
    resource_instance="HARBORSTONE-2024-0042",
)


def _line(label: str, value: object) -> None:
    print(f"  {label:<34} {value}")


def main() -> int:
    print("CompliIdentity live-wiring check")
    print("=" * 70)

    base_url = os.environ.get("COMPLIIDENTITY_BASE_URL")
    service_principal_id = os.environ.get("COMPLIIDENTITY_SERVICE_PRINCIPAL_ID")
    bearer = os.environ.get("COMPLIIDENTITY_BEARER_TOKEN")

    _line("COMPLIIDENTITY_BASE_URL", base_url or "(unset)")
    _line("COMPLIIDENTITY_SERVICE_PRINCIPAL_ID", service_principal_id or "(unset)")
    _line("COMPLIIDENTITY_BEARER_TOKEN", "(set)" if bearer else "(unset)")

    client = authority_context_service.default_client()
    if client is None:
        print("-" * 70)
        print(
            "NOT LIVE: default_client() returned None -- BASE_URL or "
            "SERVICE_PRINCIPAL_ID is unset. Every authority-gated decision "
            "fails closed (UNAVAILABLE -> ESCALATED)."
        )
        return 1

    reachable = client.health_check()
    _line("health_check() (GET /health)", "ok" if reachable else "FAILED")

    ctx = client.fetch(**_PROBE)
    print("-" * 70)
    _line("probe", "AIRA aml.action:propose @ HARBORSTONE-2024-0042")
    _line("AuthorityContext.status", ctx.status)
    _line("  reason", ctx.reason)
    _line("  permission_present", ctx.permission_present)
    _line("  sufficient", ctx.sufficient)
    _line("  findings", list(ctx.findings))
    _line("  authority_revision", ctx.authority_revision)
    _line("  integrity_content_hash", ctx.integrity_content_hash)
    print("=" * 70)

    if ctx.status in ("OK", "KNOWN_DENIED"):
        print(
            f"LIVE: real authority-context response ({ctx.status}). Decision "
            "engine calls are reaching CompliIdentity, not falling back."
        )
        return 0

    print(
        f"NOT LIVE: probe normalized to {ctx.status} (reason: {ctx.reason}). "
        "The engine would fail closed on every authority-gated decision. "
        "Check that CompliIdentity is up on the URL above and that the "
        "service principal id matches the running instance."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
