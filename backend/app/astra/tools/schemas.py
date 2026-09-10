"""OpenAI function-calling JSON schemas for the four Astra tools.

Responses API flat-tool form: ``{"type": "function", "name", "description",
"parameters", "strict"}``. ``strict`` + ``additionalProperties: false`` +
every property listed in ``required`` (nullable via a union type where the
argument is genuinely optional) keeps the model's tool calls well-formed.

There are exactly four schemas. There is no schema for an execution tool.
``tools_for_persona`` only ever returns the subset a persona is allowed to
call, so the wire request to the model never carries more than that.
"""

from __future__ import annotations

from typing import Any

from app.astra.personas import (
    TOOL_GET_AUTHORIZED_TRANSACTION_HISTORY,
    TOOL_GET_CASE_DATA,
    TOOL_PROPOSE_GOVERNED_ACTION,
    TOOL_REQUEST_SANCTIONS_SCREENING,
    Persona,
)

_CASE_DATA_SECTIONS = ["case", "kyc", "counterparties", "recent_decisions"]

_GET_CASE_DATA: dict[str, Any] = {
    "type": "function",
    "name": TOOL_GET_CASE_DATA,
    "description": (
        "Read approved, validated data for the single AML case this session is "
        "scoped to: case/target metadata, the latest KYC/screening evidence "
        "claims, known counterparties, and recent governance decisions. "
        "Returns only records that have passed validation. Read-only."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "required": ["case_id", "sections"],
        "properties": {
            "case_id": {
                "type": "string",
                "description": (
                    "The case identifier. Must be the case this session is "
                    "scoped to; any other value is refused."
                ),
            },
            "sections": {
                "type": ["array", "null"],
                "description": "Which sections to return. Null returns all.",
                "items": {"type": "string", "enum": _CASE_DATA_SECTIONS},
            },
        },
    },
}

_GET_AUTHORIZED_TRANSACTION_HISTORY: dict[str, Any] = {
    "type": "function",
    "name": TOOL_GET_AUTHORIZED_TRANSACTION_HISTORY,
    "description": (
        "Read the authorized transaction history for the case in scope: "
        "transfer/payment intents that reached an APPROVED governance decision "
        "(and, where present, an issued execution authorization). Does not "
        "include denied, escalated, or never-proposed transactions. Read-only."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "required": ["case_id", "limit", "direction"],
        "properties": {
            "case_id": {
                "type": "string",
                "description": "The case identifier. Must be the session's case.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "description": "Maximum records to return, newest first.",
            },
            "direction": {
                "type": ["string", "null"],
                "enum": ["inbound", "outbound", None],
                "description": "Optional direction filter.",
            },
        },
    },
}

_REQUEST_SANCTIONS_SCREENING: dict[str, Any] = {
    "type": "function",
    "name": TOOL_REQUEST_SANCTIONS_SCREENING,
    "description": (
        "Delegate a sanctions-screening task to SENTRY for one subject. SENTRY "
        "runs the screening connector and returns a structured, "
        "integrity-hashed result (NO_MATCH / POTENTIAL_MATCH / "
        "CONFIRMED_MATCH / NOT_EVALUABLE, a risk level, and a "
        "requires_human_review flag). Screening only -- it does not approve, "
        "deny, freeze, or restrict anything. NOTE: in this environment the "
        "screening lookup runs against a fixed demo dataset "
        "(result.simulation == true); everything downstream of the result is "
        "real."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "required": ["subject_id", "subject_type", "reason"],
        "properties": {
            "subject_id": {
                "type": "string",
                "description": (
                    "Identifier of the subject to screen (e.g. a wallet or "
                    "account id)."
                ),
            },
            "subject_type": {
                "type": "string",
                "enum": ["wallet", "account", "entity", "individual"],
                "description": "Kind of subject being screened.",
            },
            "reason": {
                "type": ["string", "null"],
                "description": (
                    "Short reason for the screening request, recorded on the "
                    "evidence item's provenance."
                ),
            },
        },
    },
}

_PROPOSE_GOVERNED_ACTION: dict[str, Any] = {
    "type": "function",
    "name": TOOL_PROPOSE_GOVERNED_ACTION,
    "description": (
        "Propose one consequential action for governance evaluation. This is a "
        "terminal step: the proposal flows through the CompliIdentity "
        "authority check, the CompliAGL decision engine, human approval when "
        "escalated, and execution by the application. You are proposing, not "
        "executing -- you receive the governance decision (APPROVED / DENIED / "
        "ESCALATED) and nothing else. Use for actions such as initiating a "
        "transfer, requesting data access, or triggering a workflow step."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "action_type",
            "compliidentity_resource",
            "compliidentity_action",
            "resource_instance",
            "target_identifier",
            "rationale",
            "amount_minor",
            "amount_currency",
            "parameters",
        ],
        "properties": {
            "action_type": {
                "type": "string",
                "enum": ["transfer", "data_access", "workflow_action"],
                "description": "Coarse class of the proposed action.",
            },
            "compliidentity_resource": {
                "type": "string",
                "description": (
                    "CompliIdentity resource for the authority probe, e.g. "
                    "'aml.action', 'aml.case', 'sanctions.screening'."
                ),
            },
            "compliidentity_action": {
                "type": "string",
                "enum": ["propose", "read"],
                "description": (
                    "Semantic verb for the authority probe. 'approve' is not "
                    "available to you."
                ),
            },
            "resource_instance": {
                "type": "string",
                "description": (
                    "The case id the action is scoped to. Must be the "
                    "session's case."
                ),
            },
            "target_identifier": {
                "type": ["string", "null"],
                "description": (
                    "The subject the action acts on -- e.g. a transfer "
                    "destination or counterparty wallet. This is what gets "
                    "sanctions-screened. Null to act on the case itself."
                ),
            },
            "rationale": {
                "type": "string",
                "description": (
                    "Why this action is being proposed. Recorded on the intent."
                ),
            },
            "amount_minor": {
                "type": ["integer", "null"],
                "minimum": 0,
                "description": (
                    "Monetary amount in integer minor units (e.g. cents). Null "
                    "if the action is not monetary."
                ),
            },
            "amount_currency": {
                "type": ["string", "null"],
                "description": (
                    "ISO 4217 currency code. Required when amount_minor is "
                    "set, otherwise null."
                ),
            },
            # Bounded, strict-mode-compatible: a closed object with a small set
            # of known optional keys (every one required + nullable, per strict
            # mode), not an open-ended dict. The handler flattens these into
            # ``intent.parameters`` and also derives ``counterparty`` from
            # ``target_identifier``.
            "parameters": {
                "type": ["object", "null"],
                "description": (
                    "Optional extra structured parameters for the intent "
                    "(non-monetary)."
                ),
                "additionalProperties": False,
                "required": ["direction", "note"],
                "properties": {
                    "direction": {
                        "type": ["string", "null"],
                        "enum": ["inbound", "outbound", None],
                        "description": "Direction of the action, if applicable.",
                    },
                    "note": {
                        "type": ["string", "null"],
                        "description": (
                            "Free-text note recorded on the intent parameters."
                        ),
                    },
                },
            },
        },
    },
}

SCHEMAS_BY_NAME: dict[str, dict[str, Any]] = {
    TOOL_GET_CASE_DATA: _GET_CASE_DATA,
    TOOL_GET_AUTHORIZED_TRANSACTION_HISTORY: _GET_AUTHORIZED_TRANSACTION_HISTORY,
    TOOL_REQUEST_SANCTIONS_SCREENING: _REQUEST_SANCTIONS_SCREENING,
    TOOL_PROPOSE_GOVERNED_ACTION: _PROPOSE_GOVERNED_ACTION,
}


def all_schemas() -> list[dict[str, Any]]:
    """Every tool schema, in a stable order."""
    return [SCHEMAS_BY_NAME[name] for name in SCHEMAS_BY_NAME]


def tools_for_persona(persona: Persona) -> list[dict[str, Any]]:
    """The schema objects this persona is allowed to call, in a stable order.

    This is the only thing that should ever be serialized into a Responses API
    ``tools`` array -- it never contains a tool outside ``persona.allowed_tools``.
    """
    return [
        SCHEMAS_BY_NAME[name]
        for name in SCHEMAS_BY_NAME
        if name in persona.allowed_tools
    ]
