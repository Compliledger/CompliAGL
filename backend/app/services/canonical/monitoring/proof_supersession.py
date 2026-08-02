"""Proof supersession — a new AIProof supersedes, never deletes, the prior one.

When a re-evaluation produces a new decision, the prior AIProof no longer
reflects the current governed outcome. Rather than delete it (which would break
auditability), a **new** AIProof is generated and signed, linked to the prior via
``prior_aiproof_id`` / ``superseded_aiproof_ids``, and the prior proof row is
marked ``SUPERSEDED`` with a forward ``superseded_by_aiproof_id`` link.

Both proofs remain independently retrievable and verifiable, and the supersession
is announced to the sync portals via ``proof.superseded``.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.canonical_aiproof import CanonicalAIProof
from app.models.decision import Decision
from app.repositories.canonical import (
    CanonicalAIProofRepository,
    IntentRepository,
)
from app.schemas.canonical.aiproof import AIProof, AIProofStatus, GovernedOutcome
from app.services.canonical.aiproof import generator
from app.services.canonical.aiproof import service as aiproof_service
from app.utils.canonical_enums import DecisionOutcome
from app.utils.timestamps import utc_now

# Map a re-evaluation decision outcome to the AIProof governed-outcome category.
_OUTCOME_TO_GOVERNED = {
    DecisionOutcome.APPROVED.value: GovernedOutcome.REMEDIATED_AND_REEVALUATED,
    DecisionOutcome.DENIED.value: GovernedOutcome.DENIED,
    DecisionOutcome.ESCALATED.value: GovernedOutcome.ESCALATED,
}

# Envelope / derived fields recomputed by the generator — never cloned forward.
_NON_CONTENT_FIELDS = {
    "status",
    "issuer",
    "signer_key_id",
    "aiproof_hash",
    "signature",
    "component_hashes",
    "canonicalization_algorithm",
    "hash_algorithm",
}


def _decision_ref(decision: Decision) -> dict[str, Any]:
    return {
        "decision_id": decision.id,
        "outcome": decision.outcome,
        "reason_codes": json.loads(decision.reason_codes or "[]"),
        "policy_version": decision.policy_version,
        "engine_version": decision.engine_version,
        "supersession_status": decision.supersession_status,
        "prior_decision_id": decision.prior_decision_id,
        "decision_hash": decision.decision_hash,
    }


def _governed_outcome(decision: Decision) -> GovernedOutcome:
    return _OUTCOME_TO_GOVERNED.get(
        decision.outcome, GovernedOutcome.REMEDIATED_AND_REEVALUATED
    )


def _build_from_prior(
    prior: AIProof, new_decision: Decision, new_aiproof_id: str
) -> dict[str, Any]:
    """Clone the prior proof's projections, swapping in the new decision."""
    content = prior.model_dump(mode="json")
    for field in _NON_CONTENT_FIELDS:
        content.pop(field, None)

    metadata = dict(content.get("metadata") or {})
    metadata["aiproof_id"] = new_aiproof_id
    metadata["governed_outcome"] = _governed_outcome(new_decision).value
    content["metadata"] = metadata

    content["decision"] = _decision_ref(new_decision)
    content["timestamps"] = {
        **(content.get("timestamps") or {}),
        "generated_at": utc_now().isoformat(),
    }

    prior_superseded = list(content.get("superseded_aiproof_ids") or [])
    if prior.prior_aiproof_id and prior.prior_aiproof_id not in prior_superseded:
        prior_superseded.append(prior.prior_aiproof_id)
    prior_proof_id = prior.metadata.aiproof_id
    if prior_proof_id not in prior_superseded:
        prior_superseded.append(prior_proof_id)
    content["prior_aiproof_id"] = prior_proof_id
    content["superseded_aiproof_ids"] = prior_superseded
    return content


def _build_minimal(
    db: Session,
    organization_id: str,
    new_decision: Decision,
    new_aiproof_id: str,
    *,
    correlation_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build a minimal proof when the intent has no prior proof to clone."""
    actor_identity_id = "unknown"
    intent = IntentRepository(db).get(organization_id, new_decision.intent_id)
    if intent is not None and getattr(intent, "actor_id", None):
        actor_identity_id = intent.actor_id
    return {
        "metadata": {
            "aiproof_id": new_aiproof_id,
            "organization_id": organization_id,
            "governance_evaluation_id": new_decision.governance_evaluation_id,
            "correlation_id": correlation_id,
            "governed_outcome": _governed_outcome(new_decision).value,
        },
        "actor_identity": {"actor_identity_id": actor_identity_id},
        "intent": {"intent_id": new_decision.intent_id},
        "decision": _decision_ref(new_decision),
        "timestamps": {"generated_at": utc_now().isoformat()},
        "prior_aiproof_id": None,
        "superseded_aiproof_ids": [],
    }


def supersede_proof(
    db: Session,
    organization_id: str,
    new_decision: Decision,
    *,
    prior_aiproof_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> tuple[CanonicalAIProof, Optional[CanonicalAIProof]]:
    """Generate a new AIProof superseding the prior proof (if any).

    Returns ``(new_proof_row, prior_proof_row)``. The prior proof is not deleted:
    it is marked ``SUPERSEDED`` and linked forward to the new proof.
    """
    import uuid

    repo = CanonicalAIProofRepository(db)
    prior_row: Optional[CanonicalAIProof] = None
    if prior_aiproof_id is not None:
        prior_row = repo.get(organization_id, prior_aiproof_id)
    if prior_row is None:
        prior_row = repo.current_for_intent(organization_id, new_decision.intent_id)

    new_aiproof_id = f"aiproof-{uuid.uuid4()}"
    if prior_row is not None:
        prior_proof = aiproof_service.get_aiproof(
            db, organization_id, prior_row.id
        )
        content = _build_from_prior(prior_proof, new_decision, new_aiproof_id)
        if correlation_id and content["metadata"].get("correlation_id") is None:
            content["metadata"]["correlation_id"] = correlation_id
    else:
        content = _build_minimal(
            db,
            organization_id,
            new_decision,
            new_aiproof_id,
            correlation_id=correlation_id,
        )

    proof = generator.generate_signed_aiproof(**content)
    new_row = aiproof_service.store_aiproof(db, proof)

    if prior_row is not None and prior_row.id != new_row.id:
        prior_row.status = AIProofStatus.SUPERSEDED.value
        prior_row.superseded_by_aiproof_id = new_row.id
        repo.save(prior_row)
        _publish_proof_superseded(db, prior_row, new_row, new_decision)

    return new_row, prior_row


def _publish_proof_superseded(
    db: Session,
    prior_row: CanonicalAIProof,
    new_row: CanonicalAIProof,
    new_decision: Decision,
) -> None:
    from app.services.canonical.integration import event_publisher
    from app.services.canonical.integration.contracts import EventContract
    from app.utils.canonical_enums import IntegrationEventType

    event_publisher.emit_safe(
        db,
        EventContract(
            event_type=IntegrationEventType.PROOF_SUPERSEDED,
            organization_id=prior_row.organization_id,
            aggregate_type="AIProof",
            aggregate_id=prior_row.id,
            references={
                "aiproof_id": prior_row.id,
                "proof_hash": prior_row.aiproof_hash,
                "superseded_by_aiproof_id": new_row.id,
                "new_proof_hash": new_row.aiproof_hash,
                "intent_id": new_decision.intent_id,
                "decision_id": new_decision.id,
            },
            attributes={
                "status": AIProofStatus.SUPERSEDED.value,
                "governed_outcome": prior_row.governed_outcome,
            },
            dedup_key=f"proof_superseded_by:{new_row.id}",
        ),
    )


def _row_entry(row: CanonicalAIProof) -> dict[str, Any]:
    return {
        "aiproof_id": row.id,
        "status": row.status,
        "governed_outcome": row.governed_outcome,
        "aiproof_hash": row.aiproof_hash,
        "prior_aiproof_id": row.prior_aiproof_id,
        "superseded_by_aiproof_id": row.superseded_by_aiproof_id,
        "decision_id": row.decision_id,
        "intent_id": row.intent_id,
        "created_at": row.created_at,
    }


def proof_chain(
    db: Session, organization_id: str, aiproof_id: str
) -> Optional[dict[str, Any]]:
    """Return the full supersession chain an AIProof belongs to."""
    repo = CanonicalAIProofRepository(db)
    anchor = repo.get(organization_id, aiproof_id)
    if anchor is None:
        return None

    root = anchor
    seen: set[str] = {root.id}
    while root.prior_aiproof_id:
        prior = repo.get(organization_id, root.prior_aiproof_id)
        if prior is None or prior.id in seen:
            break
        seen.add(prior.id)
        root = prior

    chain: list[CanonicalAIProof] = [root]
    walked: set[str] = {root.id}
    current = root
    while current.superseded_by_aiproof_id:
        nxt = repo.get(organization_id, current.superseded_by_aiproof_id)
        if nxt is None or nxt.id in walked:
            break
        walked.add(nxt.id)
        chain.append(nxt)
        current = nxt

    return {
        "anchor_aiproof_id": aiproof_id,
        "root_aiproof_id": root.id,
        "current_aiproof_id": chain[-1].id if chain else anchor.id,
        "length": len(chain),
        "chain": [_row_entry(r) for r in chain],
    }
