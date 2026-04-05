"""Proof payload schema — builds the canonical payload before hashing.

The ``build_proof_payload`` helper assembles all governance artefacts
(actor, transaction, decision, execution) into a single flat dictionary
that is later hashed and wrapped into a :class:`ProofBundle`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.mvp2.schemas.actor import ActorIdentity
from app.mvp2.schemas.decision import DecisionResult
from app.mvp2.schemas.transaction import ExecutionResult, TransactionRequest


def build_proof_payload(
    actor: ActorIdentity,
    transaction: TransactionRequest,
    decision: DecisionResult,
    execution: ExecutionResult,
) -> dict:
    """Assemble a proof payload dictionary from governance artefacts.

    This helper is called **before** hashing and creating the final
    :class:`~app.mvp2.schemas.proof.ProofBundle`.  It extracts the
    relevant fields from each schema and returns a flat dictionary
    suitable for canonical serialisation and hashing.

    Parameters
    ----------
    actor:
        The identity of the actor who initiated the transaction.
    transaction:
        The original transaction request under governance.
    decision:
        The governance decision rendered for the transaction.
    execution:
        The on-chain execution result of the transaction.

    Returns
    -------
    dict
        A dictionary containing the following keys:

        * ``actor_id``
        * ``transaction_id``
        * ``decision``
        * ``reason_codes``
        * ``policy_id``
        * ``policy_version``
        * ``execution_tx_hash``
        * ``execution_chain``
        * ``execution_status``
        * ``timestamp``
    """
    return {
        "actor_id": actor.actor_id,
        "transaction_id": transaction.transaction_id,
        "decision": decision.decision.value,
        "reason_codes": decision.reason_codes,
        "policy_id": decision.policy_id,
        "policy_version": decision.policy_version,
        "execution_tx_hash": execution.tx_hash,
        "execution_chain": execution.chain,
        "execution_status": execution.execution_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
