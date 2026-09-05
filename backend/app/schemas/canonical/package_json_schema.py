"""JSON Schema for executable governance packages, plus contract validation.

Two layers of validation are provided:

1. **Structural** — a JSON Schema (Draft 2020-12) that constrains the shape of a
   package document. Enforced with the :mod:`jsonschema` library.
2. **Referential / traceability** — cross-reference checks that guarantee the
   acceptance criteria hold: every requirement is traceable to a source
   reference, every control maps to one or more requirements, every evidence
   requirement maps to controls, and every decision condition is explicit and
   machine-readable.

These checks are deterministic and never rely on an LLM.
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

# --------------------------------------------------------------------------- #
# JSON Schema (structural)
# --------------------------------------------------------------------------- #
GOVERNANCE_PACKAGE_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://compliledger.example/schemas/executable-governance-package.json",
    "title": "ExecutableGovernancePackage",
    "type": "object",
    "additionalProperties": True,
    "required": [
        "package_name",
        "package_version",
        "content_schema_version",
        "requirements",
        "control_definitions",
        "decision_conditions",
    ],
    "properties": {
        "package_name": {"type": "string", "minLength": 1},
        "package_version": {"type": "string", "minLength": 1},
        "content_schema_version": {"type": "string", "minLength": 1},
        "source_document_references": {"type": "array"},
        "source_requirement_references": {"type": "array"},
        "requirements": {
            "type": "array",
            "items": {"$ref": "#/$defs/requirement"},
        },
        "applicability_rules": {"type": "array"},
        "control_definitions": {
            "type": "array",
            "items": {"$ref": "#/$defs/control"},
        },
        "evidence_requirements": {
            "type": "array",
            "items": {"$ref": "#/$defs/evidence_requirement"},
        },
        "decision_conditions": {
            "type": "array",
            "items": {"$ref": "#/$defs/decision_condition"},
        },
        "conflict_resolution_rules": {"type": "array"},
        "metadata": {"type": "object"},
        "requires_authority_context": {"type": "boolean"},
    },
    "$defs": {
        "requirement": {
            "type": "object",
            "additionalProperties": True,
            "required": [
                "requirement_id",
                "source_reference",
                "normalized_text",
                "requirement_type",
                "classification",
            ],
            "properties": {
                "requirement_id": {"type": "string", "minLength": 1},
                "source_reference": {"type": "string", "minLength": 1},
                "normalized_text": {"type": "string", "minLength": 1},
                "requirement_type": {"type": "string", "minLength": 1},
                "classification": {
                    "type": "string",
                    "enum": ["OBLIGATION", "PROHIBITION", "PERMISSION"],
                },
                "applicability_expression": {"type": ["string", "null"]},
                "mapped_control_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "severity": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                },
            },
        },
        "control": {
            "type": "object",
            "additionalProperties": True,
            "required": [
                "control_id",
                "requirement_ids",
                "control_objective",
                "evaluation_expression",
            ],
            "properties": {
                "control_id": {"type": "string", "minLength": 1},
                "requirement_ids": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "control_objective": {"type": "string", "minLength": 1},
                "evaluation_expression": {"type": "string", "minLength": 1},
                "mandatory": {"type": "boolean"},
                "severity": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                },
                "failure_disposition": {
                    "type": "string",
                    "enum": [
                        "DENY",
                        "ESCALATE",
                        "FLAG",
                        "ALLOW_WITH_REMEDIATION",
                    ],
                },
                "remediation_eligible": {"type": "boolean"},
                "evidence_requirement_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "decision_impact": {"type": "object"},
            },
        },
        "evidence_requirement": {
            "type": "object",
            "additionalProperties": True,
            "required": [
                "evidence_requirement_id",
                "control_ids",
                "evidence_type",
                "authoritative_source_type",
            ],
            "properties": {
                "evidence_requirement_id": {"type": "string", "minLength": 1},
                "control_ids": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "evidence_type": {"type": "string", "minLength": 1},
                "authoritative_source_type": {"type": "string", "minLength": 1},
                "minimum_cardinality": {"type": "integer", "minimum": 0},
                "mandatory": {"type": "boolean"},
                "allowed_issuers": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "metadata": {"type": "object"},
            },
        },
        "decision_condition": {
            "type": "object",
            "additionalProperties": True,
            "required": [
                "condition_id",
                "expression",
                "resulting_decision",
                "reason_code",
            ],
            "properties": {
                "condition_id": {"type": "string", "minLength": 1},
                "expression": {"type": "string", "minLength": 1},
                "resulting_decision": {
                    "type": "string",
                    "enum": ["APPROVED", "DENIED", "ESCALATED"],
                },
                "priority": {"type": "integer", "minimum": 0},
                "reason_code": {"type": "string", "minLength": 1},
                "terminal": {"type": "boolean"},
            },
        },
    },
}

_validator = Draft202012Validator(GOVERNANCE_PACKAGE_JSON_SCHEMA)


def validate_package_document(document: dict[str, Any]) -> list[str]:
    """Validate a package document and return a list of error messages.

    An empty list means the document satisfies both the structural JSON Schema
    and the referential/traceability rules required by the contract.
    """
    errors: list[str] = []

    # -- Structural (JSON Schema) ----------------------------------------- #
    for err in sorted(_validator.iter_errors(document), key=lambda e: e.path):
        location = "/".join(str(p) for p in err.path) or "<root>"
        errors.append(f"schema[{location}]: {err.message}")

    # If the structure is invalid, referential checks may raise; guard them.
    requirements = document.get("requirements") or []
    controls = document.get("control_definitions") or []
    evidence = document.get("evidence_requirements") or []
    conditions = document.get("decision_conditions") or []

    if not isinstance(requirements, list) or not isinstance(controls, list):
        return errors  # structural errors already recorded

    requirement_ids = {
        r.get("requirement_id")
        for r in requirements
        if isinstance(r, dict) and r.get("requirement_id")
    }
    control_ids = {
        c.get("control_id")
        for c in controls
        if isinstance(c, dict) and c.get("control_id")
    }
    evidence_ids = {
        e.get("evidence_requirement_id")
        for e in evidence
        if isinstance(e, dict) and e.get("evidence_requirement_id")
    }

    # -- Traceability: every requirement has a source reference ----------- #
    for req in requirements:
        if not isinstance(req, dict):
            continue
        rid = req.get("requirement_id", "<unknown>")
        if not req.get("source_reference"):
            errors.append(
                f"traceability: requirement '{rid}' has no source_reference"
            )

    # -- Every control maps to one or more existing requirements ---------- #
    for ctrl in controls:
        if not isinstance(ctrl, dict):
            continue
        cid = ctrl.get("control_id", "<unknown>")
        req_ids = ctrl.get("requirement_ids") or []
        if not req_ids:
            errors.append(f"traceability: control '{cid}' maps to no requirements")
        for rid in req_ids:
            if rid not in requirement_ids:
                errors.append(
                    f"traceability: control '{cid}' references unknown "
                    f"requirement '{rid}'"
                )
        for eid in ctrl.get("evidence_requirement_ids") or []:
            if eid not in evidence_ids:
                errors.append(
                    f"traceability: control '{cid}' references unknown "
                    f"evidence requirement '{eid}'"
                )

    # -- Every evidence requirement maps to existing controls ------------- #
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        eid = ev.get("evidence_requirement_id", "<unknown>")
        ctrl_ids = ev.get("control_ids") or []
        if not ctrl_ids:
            errors.append(
                f"traceability: evidence requirement '{eid}' maps to no controls"
            )
        for cid in ctrl_ids:
            if cid not in control_ids:
                errors.append(
                    f"traceability: evidence requirement '{eid}' references "
                    f"unknown control '{cid}'"
                )

    # -- Requirement -> control mappings must resolve --------------------- #
    for req in requirements:
        if not isinstance(req, dict):
            continue
        rid = req.get("requirement_id", "<unknown>")
        for cid in req.get("mapped_control_ids") or []:
            if cid not in control_ids:
                errors.append(
                    f"traceability: requirement '{rid}' maps to unknown "
                    f"control '{cid}'"
                )

    # -- Decision conditions must be explicit and machine-readable -------- #
    if not conditions:
        errors.append("decision: package has no decision_conditions")
    seen_condition_ids: set[str] = set()
    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        cond_id = cond.get("condition_id")
        if cond_id in seen_condition_ids:
            errors.append(f"decision: duplicate condition_id '{cond_id}'")
        if cond_id:
            seen_condition_ids.add(cond_id)

    return errors
