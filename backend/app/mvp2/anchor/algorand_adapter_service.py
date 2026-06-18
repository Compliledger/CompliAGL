"""CompliAGL wrapper around the shared ``compliledger-algorand-adapter``.

This module is a **thin integration layer**. All Algorand anchoring logic —
the Algorand client, hashing, transaction builder, and on-chain registry —
lives in the shared ``compliledger-algorand-adapter`` repository and is
*reused* here rather than reimplemented.

The wrapper does only two things:

1. Map a CompliAGL **AIProof** bundle onto the adapter's canonical
   :class:`ProofSchema` (:func:`build_proof_schema_from_aiproof`).
2. Delegate anchoring and verification to the adapter's services
   (:func:`anchor_ai_proof_bundle`, :func:`verify_anchored_proof`).

The shared adapter is an optional dependency. It is imported lazily so the
rest of CompliAGL keeps working (and remains importable/testable) even when
the adapter is not installed. See ``backend/app/mvp2/anchor/README.md`` for
installation instructions (the preferred local/dev option is an editable
install).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# ── Constant mapping values (CompliAGL → shared adapter ProofSchema) ──────
MODULE_NAME = "CompliAGL"
STATE_TYPE = "autonomous_execution"
CHAIN = "algorand"

# Distribution name of the shared adapter (used to resolve its version).
ADAPTER_DIST_NAME = "compliledger-algorand-adapter"


# ---------------------------------------------------------------------------
# Adapter import / version helpers
# ---------------------------------------------------------------------------


def _load_adapter() -> tuple[Any, Any, Any, Any]:
    """Import and return the shared adapter symbols used by this wrapper.

    Returns a tuple of
    ``(anchor_proof_state, get_verified_state, ProofSchema, hash_proof_payload)``.

    Raises
    ------
    ImportError
        If the shared ``compliledger-algorand-adapter`` is not installed,
        with a message describing how to install it.
    """
    try:
        from models.proof_schema import ProofSchema
        from services.anchor_service import anchor_proof_state
        from services.verification_service import get_verified_state
        from utils.hashing import hash_proof_payload
    except ImportError as exc:  # pragma: no cover - exercised when adapter absent
        raise ImportError(
            "The shared 'compliledger-algorand-adapter' is required for "
            "anchoring but is not installed. Install it locally (editable) "
            "with e.g. `pip install -e ../compliledger-algorand-adapter`. "
            "See backend/app/mvp2/anchor/README.md for details."
        ) from exc
    return anchor_proof_state, get_verified_state, ProofSchema, hash_proof_payload


def _adapter_version() -> str:
    """Return the installed version of the shared adapter, or ``"unknown"``."""
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version(ADAPTER_DIST_NAME)
        except PackageNotFoundError:
            return "unknown"
    except Exception:  # pragma: no cover - importlib.metadata always present on 3.8+
        return "unknown"


# ---------------------------------------------------------------------------
# AIProof field access helpers
# ---------------------------------------------------------------------------


def _field(bundle: Any, name: str, default: Any = None) -> Any:
    """Read *name* from an AIProof *bundle* that is a dict or an object."""
    if isinstance(bundle, dict):
        return bundle.get(name, default)
    return getattr(bundle, name, default)


def _proof_schema_fields(proof_bundle: Any) -> dict[str, Any]:
    """Map a CompliAGL AIProof bundle to shared adapter ``ProofSchema`` kwargs.

    The mapping is intentionally explicit so the contract between CompliAGL
    and the shared adapter is easy to audit:

    ====================  ====================================================
    ProofSchema field     CompliAGL AIProof source
    ====================  ====================================================
    ``module_name``       constant ``"CompliAGL"``
    ``asset_id``          ``actor_id`` or ``intent_id``
    ``state_type``        constant ``"autonomous_execution"``
    ``decision_status``   ``decision``
    ``policy_version``    ``policy_version``
    ``proof_snapshot_hash`` ``proof_hash``
    ``timestamp``         ``created_at``
    ``reason_codes``      ``decision_reason`` or ``reason_codes``
    ``metadata``          actor identity, intent, execution adapter, payment
                          protocol/reference, settlement chain, x402 status
    ====================  ====================================================
    """
    asset_id = _field(proof_bundle, "actor_id") or _field(proof_bundle, "intent_id")
    reason_codes = _field(proof_bundle, "decision_reason") or _field(
        proof_bundle, "reason_codes"
    )

    metadata = {
        "actor": _field(proof_bundle, "actor_identity") or _field(proof_bundle, "actor"),
        "intent": _field(proof_bundle, "intent"),
        "execution_adapter": _field(proof_bundle, "execution_adapter"),
        "payment_protocol": _field(proof_bundle, "payment_protocol"),
        "payment_reference": _field(proof_bundle, "payment_reference"),
        "settlement_chain": _field(proof_bundle, "settlement_chain"),
        "x402_status": _field(proof_bundle, "execution_status")
        or _field(proof_bundle, "x402_status"),
    }

    return {
        "module_name": MODULE_NAME,
        "asset_id": asset_id,
        "state_type": STATE_TYPE,
        "decision_status": _field(proof_bundle, "decision"),
        "policy_version": _field(proof_bundle, "policy_version"),
        "proof_snapshot_hash": _field(proof_bundle, "proof_hash"),
        "timestamp": _field(proof_bundle, "created_at"),
        "reason_codes": reason_codes,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_proof_schema_from_aiproof(proof_bundle: Any) -> Any:
    """Build a shared adapter ``ProofSchema`` from a CompliAGL AIProof bundle.

    Parameters
    ----------
    proof_bundle:
        A CompliAGL AIProof bundle (dict or object) describing an autonomous
        execution: identity, intent, decision, policy version, proof hash,
        and execution/payment context.

    Returns
    -------
    ProofSchema
        The shared adapter's canonical proof schema instance.
    """
    _anchor, _verify, ProofSchema, _hash = _load_adapter()
    return ProofSchema(**_proof_schema_fields(proof_bundle))


def anchor_ai_proof_bundle(proof_bundle: Any) -> dict[str, Any]:
    """Anchor a CompliAGL AIProof bundle via the shared adapter.

    Delegates the actual on-chain anchoring to the shared adapter's
    ``services.anchor_service.anchor_proof_state`` and normalises its result
    into a CompliAGL **anchor receipt**.

    Returns
    -------
    dict
        An anchor receipt with the keys ``chain``, ``network``,
        ``proof_hash``, ``txid``, ``explorer_url``, ``anchored_at``,
        ``adapter`` and ``adapter_version``.
    """
    anchor_proof_state, _verify, ProofSchema, _hash = _load_adapter()

    schema = ProofSchema(**_proof_schema_fields(proof_bundle))
    anchored = anchor_proof_state(schema)

    proof_hash = (
        _field(anchored, "proof_snapshot_hash")
        or _field(anchored, "proof_hash")
        or _field(schema, "proof_snapshot_hash")
    )

    return {
        "chain": CHAIN,
        "network": _field(anchored, "network"),
        "proof_hash": proof_hash,
        "txid": _field(anchored, "txid") or _field(anchored, "tx_id"),
        "explorer_url": _field(anchored, "explorer_url"),
        "anchored_at": (
            _field(anchored, "anchored_at")
            or _field(anchored, "timestamp")
            or datetime.now(timezone.utc).isoformat()
        ),
        "adapter": ADAPTER_DIST_NAME,
        "adapter_version": _adapter_version(),
    }


def verify_anchored_proof(
    asset_id: str,
    module_name: str = MODULE_NAME,
    state_type: str = STATE_TYPE,
) -> Any:
    """Verify a previously anchored proof via the shared adapter.

    Delegates to the shared adapter's
    ``services.verification_service.get_verified_state``.

    Parameters
    ----------
    asset_id:
        The anchored asset/state identifier (CompliAGL ``actor_id`` or
        ``intent_id``).
    module_name:
        Anchoring module name. Defaults to ``"CompliAGL"``.
    state_type:
        Anchored state type. Defaults to ``"autonomous_execution"``.

    Returns
    -------
    The verified state as returned by the shared adapter.
    """
    _anchor, get_verified_state, _schema, _hash = _load_adapter()
    return get_verified_state(asset_id, module_name, state_type)
