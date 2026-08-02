"""Formal CompliLedger proof-handoff interface.

CompliAGL hands a signed AIProof to CompliLedger for anchoring / attestation.
The handoff is a formal contract: :func:`build_handoff_payload` produces the
:class:`CompliLedgerProofHandoff` wire payload, and :class:`CompliLedgerHandoff`
is the interface any handoff transport (HTTP client, message bus, on-chain
anchor adapter, ...) must satisfy.

The default :class:`LocalCompliLedgerHandoff` is a deterministic, dependency-free
implementation used for local/dev flows and tests: it independently verifies the
proof before "accepting" it, mirroring what a real CompliLedger endpoint must do.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel

from app.schemas.canonical.aiproof import (
    AIProof,
    AIPROOF_SCHEMA_VERSION,
    CompliLedgerProofHandoff,
    HandoffStatus,
)
from app.services.canonical.aiproof.verify import verify_aiproof


class HandoffResult(BaseModel):
    """Result returned by a CompliLedger handoff transport."""

    status: HandoffStatus
    reference: Optional[str] = None
    detail: Optional[str] = None


@runtime_checkable
class CompliLedgerHandoff(Protocol):
    """Interface every CompliLedger handoff transport must satisfy."""

    def submit(self, handoff: CompliLedgerProofHandoff) -> HandoffResult:
        """Submit a handoff payload to CompliLedger and return the result."""
        ...


def build_handoff_payload(
    proof: AIProof,
    *,
    requested_proof_policy: Optional[str] = None,
    privacy_classification: Optional[str] = None,
) -> CompliLedgerProofHandoff:
    """Build the :class:`CompliLedgerProofHandoff` payload for a signed *proof*.

    ``privacy_classification`` defaults to the proof's most restrictive evidence
    source classification when not supplied, so the handoff always carries an
    explicit privacy posture.
    """
    if not proof.signature or not proof.aiproof_hash:
        raise ValueError("AIProof must be signed before it can be handed off")

    classification = privacy_classification or _derive_privacy_classification(proof)
    return CompliLedgerProofHandoff(
        aiproof_id=proof.metadata.aiproof_id,
        schema_version=proof.metadata.schema_version or AIPROOF_SCHEMA_VERSION,
        canonical_aiproof=proof,
        aiproof_hash=proof.aiproof_hash,
        signature=proof.signature,
        signer_identity=proof.issuer,
        signer_key_id=proof.signer_key_id,
        organization_id=proof.metadata.organization_id,
        requested_proof_policy=requested_proof_policy,
        privacy_classification=classification,
        correlation_id=proof.metadata.correlation_id,
    )


# Order from least to most restrictive so the maximum can be selected.
_CLASSIFICATION_ORDER = [
    "PUBLIC",
    "INTERNAL",
    "CONFIDENTIAL",
    "PII",
    "SENSITIVE",
    "SECRET",
]


def _derive_privacy_classification(proof: AIProof) -> str:
    """Return the most restrictive evidence source classification in *proof*."""
    worst = 0
    seen = False
    for ref in proof.evidence_references:
        cls = (ref.source_classification or "").upper()
        if cls in _CLASSIFICATION_ORDER:
            seen = True
            worst = max(worst, _CLASSIFICATION_ORDER.index(cls))
    return _CLASSIFICATION_ORDER[worst] if seen else "INTERNAL"


class LocalCompliLedgerHandoff:
    """Default in-process handoff: verifies the proof, then accepts it.

    A real CompliLedger endpoint independently schema-validates and
    signature-verifies the AIProof before accepting it; this local implementation
    performs exactly those checks so the handoff contract is exercised end to end.
    """

    def submit(self, handoff: CompliLedgerProofHandoff) -> HandoffResult:
        result = verify_aiproof(handoff.canonical_aiproof)
        if not result.valid:
            return HandoffResult(
                status=HandoffStatus.REJECTED,
                detail="; ".join(result.errors) or "AIProof failed verification",
            )
        return HandoffResult(
            status=HandoffStatus.ACCEPTED,
            reference=f"compliledger:{handoff.aiproof_hash}",
            detail="AIProof accepted by CompliLedger (local handoff).",
        )


# Process-wide default handoff transport. Swap this binding to route handoffs to
# a real CompliLedger client without touching callers.
_default_handoff: CompliLedgerHandoff = LocalCompliLedgerHandoff()


def get_handoff() -> CompliLedgerHandoff:
    """Return the configured CompliLedger handoff transport."""
    return _default_handoff
