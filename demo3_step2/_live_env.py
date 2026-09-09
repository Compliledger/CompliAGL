"""Single source of truth for the CompliIdentity *live-wiring* environment.

``authority_context_service.default_client()`` reads these two values straight
from ``os.environ`` (see
``backend/app/services/canonical/authority_context_service.py``). They are
deliberately **not** ``backend/.env`` / pydantic ``Settings`` keys -- that model
is ``extra="forbid"`` and does not populate ``os.environ`` -- exactly the way
the SecureRob connector reads ``SECUREROB_GATEWAY_BASE_URL``. See
``backend/ITEM7_ASK_COMPLIIDENTITY_OWNER.md``.

Any in-process driver that runs the real deterministic decision pipeline
against a live CompliIdentity instance must::

    import _live_env  # noqa: F401  -- MUST precede any `app` import

before importing any ``app`` module, so the values are in ``os.environ`` by the
time ``default_client()`` is first called. Importing this module applies them
as a side effect.

``os.environ.setdefault`` is used, so a value already exported in the real
process environment (``$env:COMPLIIDENTITY_BASE_URL = ...`` /
``demo3_step2/live-env.ps1``) always wins over the defaults here.

Principal-id lifecycle: ``COMPLIIDENTITY_SERVICE_PRINCIPAL_ID`` is tied to the
local ``compliidentity_demo3_step2.db`` instance created by
``demo3_step2/compliidentity_setup_phases_1_7.py``. If that instance is
regenerated, CompliIdentity re-issues every principal id -- update it **here**
(the one place drivers read it from) and in ``backend/app/db/seed.py``
(``_HARBORSTONE_*_PRINCIPAL_ID``).
"""

from __future__ import annotations

import os

# Local CompliIdentity instance left live by compliidentity_setup_phases_1_7.py.
COMPLIIDENTITY_BASE_URL = "http://127.0.0.1:8137"

# CompliAGL's own service principal ("CompliAGL Service", SERVICE, tenant
# harborstone-demo) in that instance -- the X-Actor-Principal-Id CompliAGL
# authenticates as. Confirmed 2026-09-10 against the live instance
# (GET /api/v1/principals): the "CompliAGL Service" SERVICE principal is
# 0812c9a2-...; the old ae24b758-... value now returns 401 actor_unauthenticated.
# This matches CompliAegis's .env COMPLIAGL_SERVICE_PRINCIPAL_ID.
COMPLIIDENTITY_SERVICE_PRINCIPAL_ID = "0812c9a2-f1c2-4cd2-81a8-8384502ad77e"


def apply() -> dict[str, str]:
    """Apply the live-wiring env vars (setdefault) and return the effective values.

    Safe to call more than once. A pre-exported real env var is never
    overwritten.
    """
    os.environ.setdefault("COMPLIIDENTITY_BASE_URL", COMPLIIDENTITY_BASE_URL)
    os.environ.setdefault(
        "COMPLIIDENTITY_SERVICE_PRINCIPAL_ID", COMPLIIDENTITY_SERVICE_PRINCIPAL_ID
    )
    return {
        "COMPLIIDENTITY_BASE_URL": os.environ["COMPLIIDENTITY_BASE_URL"],
        "COMPLIIDENTITY_SERVICE_PRINCIPAL_ID": os.environ[
            "COMPLIIDENTITY_SERVICE_PRINCIPAL_ID"
        ],
    }


# Apply on import so drivers only need `import _live_env` before their app imports.
apply()
