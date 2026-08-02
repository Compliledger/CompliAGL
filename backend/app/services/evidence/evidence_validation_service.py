"""Evidence validation — deterministic verdict for a raw evidence item.

Validation evaluates a fixed battery of checks against a single
:class:`~app.models.raw_evidence.RawEvidence` item and collapses them into one
deterministic :class:`~app.utils.canonical_enums.EvidenceValidationOutcome`:

    schema validity, authenticity, integrity, issuer trust, signature validity
    (when applicable), subject binding, target binding, transaction/intent
    binding, freshness, expiration, revocation, replay risk and source authority.

The evaluation is pure and side-effect-free; a separate persistence helper writes
one :class:`~app.models.evidence_validation_result.EvidenceValidationResult` per
raw evidence item so *every* item receives a verdict.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.evidence_validation_result import EvidenceValidationResult
from app.models.raw_evidence import RawEvidence
from app.repositories.canonical import EvidenceValidationResultRepository
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.utils.canonical_enums import (
    EvidenceCollectionStatus,
    EvidenceValidationOutcome,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import ensure_aware, parse_iso8601_duration, utc_now


def _load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


# --------------------------------------------------------------------------- #
# Pure evaluation
# --------------------------------------------------------------------------- #
def evaluate(raw: RawEvidence, *, now=None) -> dict[str, Any]:
    """Return ``{"outcome", "checks", "reason_codes"}`` for one raw item."""
    now = ensure_aware(now) or utc_now()
    provenance = _load(raw.provenance, {}) or {}
    requirement = provenance.get("requirement", {}) or {}
    claims = _load(raw.claims, {}) or {}

    # An item that was never collected cannot be validated as VALID. It receives
    # an explicit INDETERMINATE verdict rather than a silent success.
    if raw.collection_status != EvidenceCollectionStatus.COLLECTED.value:
        checks = {
            name: None
            for name in (
                "schema_valid",
                "authenticity",
                "integrity",
                "issuer_trust",
                "signature_valid",
                "subject_binding",
                "target_binding",
                "intent_binding",
                "freshness",
                "expiration",
                "revocation",
                "replay_ok",
                "source_authority",
            )
        }
        return {
            "outcome": EvidenceValidationOutcome.INDETERMINATE.value,
            "checks": checks,
            "reason_codes": [
                f"EVIDENCE_NOT_COLLECTED_{raw.collection_status}",
            ],
        }

    allowed_issuers = list(requirement.get("allowed_issuers") or [])
    trusted_issuers = list(provenance.get("connector_trusted_issuers") or [])

    # --- schema validity --- #
    has_content = bool(claims) or raw.payload is not None or bool(
        raw.payload_reference
    )
    schema_valid = has_content

    # --- integrity (payload hash) --- #
    if raw.payload is not None:
        recomputed = hash_dict({"payload": _load(raw.payload, {})})
        integrity = recomputed == raw.payload_hash
    elif raw.payload_reference:
        # Sensitive payload held by reference — trust the bound hash's presence.
        integrity = bool(raw.payload_hash)
    elif raw.claims:
        recomputed = hash_dict({"claims": _load(raw.claims, {})})
        integrity = recomputed == raw.payload_hash
    else:
        integrity = bool(raw.payload_hash)

    # --- authenticity (issuer present) --- #
    authenticity = bool(raw.issuer)

    # --- issuer trust --- #
    if allowed_issuers:
        issuer_trust = raw.issuer in allowed_issuers
    elif trusted_issuers:
        issuer_trust = raw.issuer in trusted_issuers
    else:
        issuer_trust = True

    # --- signature validity (only when a signature is present) --- #
    if raw.signature:
        signature_valid = bool(provenance.get("signature_valid"))
    else:
        signature_valid = None

    # --- subject / target / intent binding --- #
    def _binding(expected, observed):
        if expected is None:
            return None
        return observed == expected

    subject_binding = _binding(
        requirement.get("expected_subject_id"), raw.subject_id
    )
    target_binding = _binding(
        requirement.get("expected_target_id"), raw.target_id
    )
    intent_binding = _binding(
        requirement.get("expected_intent_id"), raw.intent_id
    )

    # --- freshness --- #
    threshold = parse_iso8601_duration(requirement.get("freshness_threshold"))
    issued_at = ensure_aware(raw.issued_at)
    if threshold is None or issued_at is None:
        freshness = None
    else:
        freshness = (now - issued_at) <= threshold

    # --- expiration --- #
    expires_at = ensure_aware(raw.expires_at)
    expiration = True if expires_at is None else expires_at > now

    # --- revocation (True == not revoked) --- #
    revocation = not bool(provenance.get("revoked", False))

    # --- replay risk (True == no replay) --- #
    replay_detected = bool(
        provenance.get("replay_detected", False) or claims.get("replayed", False)
    )
    replay_ok = not replay_detected

    # --- source authority --- #
    source_authority = bool(provenance.get("source_authority", True))

    checks = {
        "schema_valid": schema_valid,
        "authenticity": authenticity,
        "integrity": integrity,
        "issuer_trust": issuer_trust,
        "signature_valid": signature_valid,
        "subject_binding": subject_binding,
        "target_binding": target_binding,
        "intent_binding": intent_binding,
        "freshness": freshness,
        "expiration": expiration,
        "revocation": revocation,
        "replay_ok": replay_ok,
        "source_authority": source_authority,
    }

    outcome, reason_codes = _decide(checks)
    return {"outcome": outcome, "checks": checks, "reason_codes": reason_codes}


def _decide(checks: dict[str, Any]) -> tuple[str, list[str]]:
    """Collapse per-check results into a single deterministic outcome."""
    O = EvidenceValidationOutcome

    # Integrity / authenticity / structural failures -> INVALID.
    if checks["schema_valid"] is False:
        return O.INVALID.value, ["EVIDENCE_SCHEMA_INVALID"]
    if checks["integrity"] is False:
        return O.INVALID.value, ["EVIDENCE_INTEGRITY_FAILED"]
    if checks["authenticity"] is False:
        return O.INVALID.value, ["EVIDENCE_NOT_AUTHENTIC"]
    if checks["signature_valid"] is False:
        return O.INVALID.value, ["EVIDENCE_SIGNATURE_INVALID"]
    if checks["replay_ok"] is False:
        return O.INVALID.value, ["EVIDENCE_REPLAY_DETECTED"]

    # Source / issuer trust -> UNTRUSTED_SOURCE.
    if checks["source_authority"] is False:
        return O.UNTRUSTED_SOURCE.value, ["EVIDENCE_SOURCE_NOT_AUTHORITATIVE"]
    if checks["issuer_trust"] is False:
        return O.UNTRUSTED_SOURCE.value, ["EVIDENCE_ISSUER_UNTRUSTED"]

    # Binding failures.
    if checks["subject_binding"] is False:
        return O.SUBJECT_MISMATCH.value, ["EVIDENCE_SUBJECT_MISMATCH"]
    if checks["target_binding"] is False:
        return O.TARGET_MISMATCH.value, ["EVIDENCE_TARGET_MISMATCH"]
    if checks["intent_binding"] is False:
        return O.INVALID.value, ["EVIDENCE_INTENT_BINDING_MISMATCH"]

    # Lifecycle failures.
    if checks["revocation"] is False:
        return O.REVOKED.value, ["EVIDENCE_REVOKED"]
    if checks["expiration"] is False:
        return O.EXPIRED.value, ["EVIDENCE_EXPIRED"]
    if checks["freshness"] is False:
        return O.STALE.value, ["EVIDENCE_STALE"]

    return O.VALID.value, ["EVIDENCE_VALID"]


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def validate_raw_evidence(
    db: Session, raw: RawEvidence
) -> EvidenceValidationResult:
    """Evaluate one raw item and persist its validation result."""
    verdict = evaluate(raw)
    result_hash = hash_dict(
        {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "raw_evidence_id": raw.id,
            "payload_hash": raw.payload_hash,
            "outcome": verdict["outcome"],
            "checks": verdict["checks"],
        }
    )
    obj = EvidenceValidationResult(
        organization_id=raw.organization_id,
        raw_evidence_id=raw.id,
        evidence_requirement_id=raw.evidence_requirement_id,
        collection_job_id=raw.collection_job_id,
        policy_resolution_id=raw.policy_resolution_id,
        outcome=verdict["outcome"],
        checks=json.dumps(verdict["checks"]),
        reason_codes=json.dumps(verdict["reason_codes"]),
        result_hash=result_hash,
    )
    return EvidenceValidationResultRepository(db).add(obj)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[EvidenceValidationResult]:
    return EvidenceValidationResultRepository(db).get(
        organization_id, resource_id
    )


def list_for_job(db: Session, organization_id: str, collection_job_id: str):
    return EvidenceValidationResultRepository(db).list_for_job(
        organization_id, collection_job_id
    )
