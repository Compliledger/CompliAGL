"""Evidence normalization — canonical projection of validated evidence.

Only evidence whose validation outcome is ``VALID`` is normalized. Normalization
transforms a source-specific item into the fixed canonical schema (subject,
target, source, issuer, normalized claims, monetary values in **integer minor
units**, a validity window, validation status and both payload hashes plus a
provenance reference).

Two guarantees are enforced here:

* **PII exclusion.** Only the source-published, non-sensitive ``claims`` are
  projected — the raw payload (which may hold PII) is never copied. Downstream
  public proofs therefore only ever see normalized claims and hashes.
* **Deterministic hashes.** ``normalized_payload_hash`` is computed only over
  stable canonical content (never over wall-clock collection timestamps), so the
  same logical evidence always yields the same hash.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.evidence_validation_result import EvidenceValidationResult
from app.models.normalized_evidence import NormalizedEvidence
from app.models.raw_evidence import RawEvidence
from app.repositories.canonical import NormalizedEvidenceRepository
from app.utils.canonical_enums import EvidenceValidationOutcome
from app.utils.hashing import hash_dict

# Minor-unit exponent by currency. Defaults to 2 for unknown currencies.
_CURRENCY_EXPONENT: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "AUD": 2,
    "CAD": 2,
    "JPY": 0,
    "KRW": 0,
    "USDC": 6,
    "USDT": 6,
    "ETH": 18,
    "BTC": 8,
}


def _load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def _to_minor_units(amount: Any, currency: str) -> Optional[int]:
    """Convert a decimal amount to integer minor units using ``Decimal``.

    Floats are never used for money; the amount is coerced via its string form
    so binary rounding cannot corrupt the value.
    """
    exponent = _CURRENCY_EXPONENT.get((currency or "").upper(), 2)
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        return None
    scaled = (value * (Decimal(10) ** exponent)).to_integral_value()
    return int(scaled)


def _normalize_monetary(value: Any) -> Any:
    """Recursively convert ``{"amount", "currency"}`` shapes to minor units."""
    if isinstance(value, dict):
        if "amount_minor" in value and "currency" in value:
            # Already in canonical form.
            return {
                "amount_minor": int(value["amount_minor"]),
                "currency": str(value["currency"]).upper(),
            }
        if "amount" in value and "currency" in value:
            minor = _to_minor_units(value["amount"], value["currency"])
            return {
                "amount_minor": minor,
                "currency": str(value["currency"]).upper(),
            }
        return {k: _normalize_monetary(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_monetary(v) for v in value]
    return value


def normalize_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Return canonical claims with monetary values in integer minor units."""
    return _normalize_monetary(dict(claims or {}))


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def normalize_valid_evidence(
    db: Session, raw: RawEvidence, validation: EvidenceValidationResult
) -> Optional[NormalizedEvidence]:
    """Normalize a single validated item, if its outcome is ``VALID``.

    Returns ``None`` for any non-``VALID`` outcome — invalid evidence is never
    normalized and is instead surfaced in the canonical package's
    ``invalid_evidence`` list.
    """
    if validation.outcome != EvidenceValidationOutcome.VALID.value:
        return None

    provenance = _load(raw.provenance, {}) or {}
    requirement = provenance.get("requirement", {}) or {}
    claims = normalize_claims(_load(raw.claims, {}) or {})

    valid_from = raw.issued_at
    valid_until = raw.expires_at

    canonical_content = {
        "evidence_type": requirement.get("evidence_type"),
        "subject": raw.subject_id,
        "target": raw.target_id,
        "source": raw.source_id,
        "issuer": raw.issuer,
        "normalized_claims": claims,
        "valid_from": valid_from.isoformat() if valid_from else None,
        "valid_until": valid_until.isoformat() if valid_until else None,
        "validation_status": validation.outcome,
        "source_payload_hash": raw.payload_hash,
    }
    normalized_payload_hash = hash_dict(canonical_content)

    obj = NormalizedEvidence(
        organization_id=raw.organization_id,
        raw_evidence_id=raw.id,
        validation_result_id=validation.id,
        evidence_requirement_id=raw.evidence_requirement_id,
        collection_job_id=raw.collection_job_id,
        policy_resolution_id=raw.policy_resolution_id,
        evidence_type=requirement.get("evidence_type"),
        subject=raw.subject_id,
        target=raw.target_id,
        source=raw.source_id,
        issuer=raw.issuer,
        normalized_claims=json.dumps(claims),
        valid_from=valid_from,
        valid_until=valid_until,
        validation_status=validation.outcome,
        source_payload_hash=raw.payload_hash,
        normalized_payload_hash=normalized_payload_hash,
        provenance_reference=f"raw_evidence:{raw.id}",
    )
    return NormalizedEvidenceRepository(db).add(obj)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[NormalizedEvidence]:
    return NormalizedEvidenceRepository(db).get(organization_id, resource_id)


def list_for_job(db: Session, organization_id: str, collection_job_id: str):
    return NormalizedEvidenceRepository(db).list_for_job(
        organization_id, collection_job_id
    )
