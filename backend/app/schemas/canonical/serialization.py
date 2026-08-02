"""ORM -> response serialization for canonical resources.

Canonical models store structured fields (metadata, parameters, state snapshots,
reason codes) as JSON *text*. This helper produces a plain dict with those
fields parsed back into native objects so the ``*Response`` schemas can validate
them. Keeping serialization in one place gives the serialization/schema-version
tests a single, deterministic surface.
"""

from __future__ import annotations

import json
from typing import Any

# JSON-text columns per model class name.
_JSON_FIELDS: dict[str, tuple[str, ...]] = {
    "ActorIdentity": ("identity_metadata",),
    "Intent": ("parameters",),
    "Target": ("target_metadata",),
    "OperationalContext": (
        "risk_state",
        "account_state",
        "allowance_state",
        "merchant_state",
        "asset_state",
        "network_state",
        "operational_state_snapshot",
        "source_references",
    ),
    "GovernanceEvaluation": ("reason_codes",),
    "Decision": ("reason_codes",),
    "ExecutionAuthorization": ("constraints",),
    "ExternalExecutionResult": ("result_payload",),
}


def orm_to_dict(obj: Any) -> dict[str, Any]:
    """Return a response-ready dict for a canonical ORM instance.

    JSON-text columns are parsed into native Python objects; invalid or empty
    JSON becomes ``None``.
    """
    json_fields = _JSON_FIELDS.get(type(obj).__name__, ())
    data = {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
    for field in json_fields:
        raw = data.get(field)
        if isinstance(raw, str):
            try:
                data[field] = json.loads(raw) if raw else None
            except (ValueError, TypeError):
                data[field] = None
    return data
