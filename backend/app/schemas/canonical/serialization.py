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
    "Decision": (
        "reason_codes",
        "decision_conditions_triggered",
        "applicable_package_ids",
        "applicable_requirement_ids",
        "control_evaluation_ids",
    ),
    "ExecutionAuthorization": (
        "constraints",
        "authorized_parameter_constraints",
    ),
    "ExternalExecutionResult": ("result_payload",),
    "ExecutableGovernancePackage": (
        "source_document_references",
        "source_requirement_references",
        "requirements",
        "applicability_rules",
        "control_definitions",
        "evidence_requirements",
        "decision_conditions",
        "conflict_resolution_rules",
        "package_metadata",
    ),
    "PolicyResolution": (
        "candidate_package_ids",
        "selected_packages",
        "conflicts",
        "selection_facts",
        "reason_codes",
    ),
    "ApplicabilityEvaluation": (
        "evaluated_expression",
        "observed_values",
        "reason_codes",
    ),
    "ApplicableControlSet": (
        "controls",
        "reason_codes",
    ),
    "EvidenceRequirementSet": (
        "evidence_requirements",
        "reason_codes",
    ),
    "EvidenceSource": (
        "supported_evidence_types",
        "trusted_issuers",
        "retry_policy",
    ),
    "EvidenceOrchestrationPlan": (
        "tasks",
        "unresolved",
        "reason_codes",
    ),
    "EvidenceCollectionJob": (
        "raw_evidence_ids",
        "failures",
        "unresolved",
        "reason_codes",
    ),
    "RawEvidence": (
        "payload",
        "claims",
        "provenance",
    ),
    "EvidenceValidationResult": (
        "checks",
        "reason_codes",
    ),
    "NormalizedEvidence": ("normalized_claims",),
    "CanonicalEvidencePackage": (
        "normalized_evidence_references",
        "requirement_mappings",
        "control_mappings",
        "missing_evidence",
        "invalid_evidence",
        "reason_codes",
    ),
    "Finding": (
        "requirement_ids",
        "control_ids",
        "evidence_gap_ids",
        "reason_codes",
    ),
    "RemediationPlan": (
        "remediation_actions",
        "required_resolution_evidence",
        "dependencies",
    ),
    "ResolutionEvidence": (
        "payload",
        "claims",
        "provenance",
        "validation_checks",
        "normalized_claims",
        "reason_codes",
    ),
    "DevSyncDispatch": (
        "payload",
        "callbacks",
    ),
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
