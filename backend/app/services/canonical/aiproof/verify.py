"""Independent local verification of a canonical AIProof.

Verification is deliberately self-contained: given only an AIProof (as a model
or a plain dict) and the signer's key, a relying party can confirm the proof is
well-formed, that its component and top-level hashes reproduce, and that the
signature is valid — without any other CompliAGL state.
"""

from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel, ValidationError

from app.schemas.canonical.aiproof import AIProof
from app.services.canonical.aiproof import signing
from app.services.canonical.aiproof.canonicalization import (
    CANONICALIZATION_ALGORITHM,
    HASH_ALGORITHM,
)
from app.services.canonical.aiproof.generator import (
    compute_aiproof_hash,
    compute_component_hashes,
)


class AIProofVerification(BaseModel):
    """Structured result of verifying an AIProof."""

    valid: bool
    schema_valid: bool
    hash_valid: bool
    component_hashes_valid: bool
    signature_valid: bool
    algorithms_recognized: bool
    aiproof_id: str | None = None
    errors: list[str] = []


def verify_aiproof(proof: Union[AIProof, dict[str, Any]]) -> AIProofVerification:
    """Verify *proof* locally and return a structured :class:`AIProofVerification`.

    The checks are:

    * **schema** — the payload validates against the canonical AIProof schema;
    * **algorithms** — the canonicalization + hash algorithm identifiers match
      the ones this verifier implements;
    * **hash** — the stored ``aiproof_hash`` reproduces from the content;
    * **component hashes** — every recorded component hash reproduces;
    * **signature** — the signature is valid for the hash and signer key id.
    """
    errors: list[str] = []

    # 1. Schema validation.
    if isinstance(proof, AIProof):
        model = proof
        schema_valid = True
    else:
        try:
            model = AIProof.model_validate(proof)
            schema_valid = True
        except ValidationError as exc:
            return AIProofVerification(
                valid=False,
                schema_valid=False,
                hash_valid=False,
                component_hashes_valid=False,
                signature_valid=False,
                algorithms_recognized=False,
                errors=[f"schema: {exc.error_count()} validation error(s)"],
            )

    aiproof_id = model.metadata.aiproof_id

    # 2. Algorithm identifiers.
    algorithms_recognized = (
        model.canonicalization_algorithm == CANONICALIZATION_ALGORITHM
        and model.hash_algorithm == HASH_ALGORITHM
    )
    if not algorithms_recognized:
        errors.append(
            "algorithms: unrecognized canonicalization/hash algorithm identifiers"
        )

    # 3. Top-level hash.
    recomputed_hash = compute_aiproof_hash(model)
    hash_valid = bool(model.aiproof_hash) and recomputed_hash == model.aiproof_hash
    if not hash_valid:
        errors.append("hash: aiproof_hash does not reproduce from content")

    # 4. Component hashes.
    recomputed_components = compute_component_hashes(model)
    component_hashes_valid = recomputed_components == dict(model.component_hashes)
    if not component_hashes_valid:
        errors.append("component_hashes: one or more component hashes do not reproduce")

    # 5. Signature.
    signature_valid = bool(model.aiproof_hash) and signing.verify(
        model.signer_key_id, model.aiproof_hash or "", model.signature
    )
    if not signature_valid:
        errors.append("signature: invalid or missing signature")

    valid = (
        schema_valid
        and algorithms_recognized
        and hash_valid
        and component_hashes_valid
        and signature_valid
    )
    return AIProofVerification(
        valid=valid,
        schema_valid=schema_valid,
        hash_valid=hash_valid,
        component_hashes_valid=component_hashes_valid,
        signature_valid=signature_valid,
        algorithms_recognized=algorithms_recognized,
        aiproof_id=aiproof_id,
        errors=errors,
    )
