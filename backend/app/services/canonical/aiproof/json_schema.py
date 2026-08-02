"""Versioned JSON Schema publication + validation for the canonical AIProof.

The AIProof JSON Schema is derived from the canonical Pydantic model and stamped
with the published schema version and a stable ``$id``. Publishing it lets any
party (CompliLedger, auditors, external systems) validate an AIProof
independently of CompliAGL's runtime.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jsonschema

from app.schemas.canonical.aiproof import AIPROOF_SCHEMA_VERSION, AIProof

# Stable schema identifier. The version segment lets consumers pin a schema.
AIPROOF_SCHEMA_ID = (
    f"https://schemas.compliagl.com/aiproof/{AIPROOF_SCHEMA_VERSION}/aiproof.schema.json"
)


@lru_cache(maxsize=1)
def aiproof_json_schema() -> dict[str, Any]:
    """Return the published, versioned AIProof JSON Schema."""
    schema = AIProof.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = AIPROOF_SCHEMA_ID
    schema["title"] = "CompliAGL AIProof"
    schema["x-aiproof-schema-version"] = AIPROOF_SCHEMA_VERSION
    return schema


def validate_against_schema(payload: dict[str, Any]) -> list[str]:
    """Validate *payload* against the published schema.

    Returns a list of human-readable error messages (empty when valid).
    """
    validator_cls = jsonschema.validators.validator_for(aiproof_json_schema())
    validator = validator_cls(aiproof_json_schema())
    return [
        f"{'/'.join(str(p) for p in err.path)}: {err.message}".lstrip("/ ")
        for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    ]


def write_schema(path: str) -> None:
    """Write the published JSON Schema to *path* (pretty-printed, sorted keys)."""
    import json

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(aiproof_json_schema(), fh, indent=2, sort_keys=True)
        fh.write("\n")
