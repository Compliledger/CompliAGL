"""AIProof bundle schema — the canonical, competition-ready proof record.

An **AIProof** bundle is the verifiable record CompliAGL produces for every
governed autonomous execution. It captures *who* acted (actor), *what* they
intended (intent), *how* it was governed (policy + decision), *how* it was
executed (execution adapter + x402 payment), and *how* it is anchored
(Algorand). A deterministic ``proof_hash`` binds the pre-anchor content
together so the bundle can be independently verified.

Hashing is deterministic and **excludes post-hash fields** — values that are
only known *after* the hash is computed (the hash itself, the on-chain anchor
transaction id, and the verification URL). See :data:`HASH_EXCLUDED_FIELDS`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Fields that are populated *after* the proof hash is computed and therefore
# must be excluded from the deterministic hash input.
HASH_EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {"proof_hash", "anchor_tx_id", "verification_url"}
)


class AIProofBundle(BaseModel):
    """Canonical AIProof bundle for a governed autonomous execution."""

    # --- Identity of the proof ---
    proof_id: str = Field(..., description="Unique identifier for this proof.")
    proof_type: str = Field(
        default="compli402.execution",
        description="Type/kind of proof (e.g. governed payment execution).",
    )

    # --- Actor ---
    actor_id: str = Field(..., description="Identifier of the acting entity.")
    actor_identity: dict | None = Field(
        default=None, description="Resolved actor identity snapshot."
    )

    # --- Intent ---
    intent_id: str = Field(..., description="Identifier of the governed intent.")
    intent: dict | None = Field(
        default=None, description="The action/amount/currency the actor intended."
    )

    # --- Policy & decision ---
    policy_id: str | None = Field(
        default=None, description="Identifier of the governing policy."
    )
    policy_version: str = Field(
        default="mvp2", description="Version of the policy that was evaluated."
    )
    decision: str = Field(..., description="Governance decision (APPROVED/DENIED/...).")
    decision_reason: list[str] = Field(
        default_factory=list, description="Machine-readable decision reason codes."
    )

    # --- Execution ---
    execution_adapter: str | None = Field(
        default=None, description="Adapter used to execute the approved action."
    )
    execution_status: str | None = Field(
        default=None, description="Execution outcome status (e.g. CONFIRMED)."
    )

    # --- Payment (x402) ---
    payment_protocol: str = Field(
        default="x402", description="Payment protocol used to gate execution."
    )
    payment_reference: str | None = Field(
        default=None, description="Settlement/payment reference for the x402 payment."
    )
    settlement_chain: str | None = Field(
        default=None, description="Network/chain the payment settled on."
    )

    # --- Anchoring (Algorand) ---
    anchor_chain: str = Field(
        default="algorand", description="Chain the proof hash is anchored to."
    )
    anchor_tx_id: str | None = Field(
        default=None,
        description="On-chain anchor transaction id (post-hash; set after anchoring).",
    )

    # --- Proof binding ---
    proof_hash: str | None = Field(
        default=None, description="Deterministic SHA-256 hash binding the bundle."
    )
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp.")
    verification_url: str | None = Field(
        default=None,
        description="URL to verify this proof (post-hash; derived from proof_hash).",
    )

    def hashable_payload(self) -> dict:
        """Return the deterministic, hashable view of this bundle.

        Post-hash fields (:data:`HASH_EXCLUDED_FIELDS`) are removed so the
        same logical execution always produces the same ``proof_hash``,
        regardless of anchoring or URL generation that happens afterwards.
        """
        data = self.model_dump(mode="json")
        for field in HASH_EXCLUDED_FIELDS:
            data.pop(field, None)
        return data
