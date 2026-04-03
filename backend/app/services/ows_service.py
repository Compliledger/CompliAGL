"""Open Wallet Standard (OWS) integration abstraction layer.

Simulates future integration with OWS-compatible wallets and policy execution.
All functions currently return mocked responses with realistic structures;
no external APIs are called.  The interface is intentionally generic so a real
OWS adapter can be swapped in later.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def prepare_wallet_action(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare an OWS wallet action for a given transaction.

    In production this would construct a compliant OWS action payload and
    submit it to the wallet provider for pre-authorisation.  For now it
    returns a realistic mocked response.

    Args:
        transaction: Dictionary containing at minimum ``agent_id``,
            ``recipient``, ``amount``, and ``currency``.

    Returns:
        A dictionary describing the prepared wallet action.
    """
    action_id = str(uuid.uuid4())
    return {
        "action_id": action_id,
        "status": "prepared",
        "wallet_address": _derive_wallet_address(transaction.get("agent_id", "")),
        "payload": {
            "recipient": transaction.get("recipient"),
            "amount": transaction.get("amount"),
            "currency": transaction.get("currency", "USD"),
            "memo": transaction.get("description", ""),
        },
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": None,  # placeholder for TTL-based expiry
        "ows_version": "0.1.0-mock",
    }


def sign_wallet_action(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Sign (authorise) an OWS wallet action.

    In production this would request a cryptographic signature from the
    wallet key-store.  The mock returns a deterministic dummy signature.

    Args:
        transaction: Dictionary with transaction details used to derive the
            signature payload.

    Returns:
        A dictionary containing the signature artefact and metadata.
    """
    payload_bytes = (
        f"{transaction.get('agent_id', '')}"
        f"{transaction.get('recipient', '')}"
        f"{transaction.get('amount', 0)}"
        f"{transaction.get('currency', 'USD')}"
    ).encode()

    signature = hashlib.sha256(payload_bytes).hexdigest()

    return {
        "action_id": str(uuid.uuid4()),
        "status": "signed",
        "signature": signature,
        "algorithm": "sha256-mock",
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "ows_version": "0.1.0-mock",
    }


def get_wallet_metadata(wallet_address: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve metadata for an OWS-compatible wallet.

    In production this would query the wallet registry or on-chain state.
    The mock returns a static metadata envelope.

    Args:
        wallet_address: The wallet address to look up.  If ``None`` a
            placeholder address is used.

    Returns:
        A dictionary of wallet metadata.
    """
    address = wallet_address or "0x" + "0" * 40
    return {
        "wallet_address": address,
        "provider": "ows-mock-provider",
        "supported_currencies": ["USD", "EUR", "BTC", "ETH"],
        "status": "active",
        "compliance_level": "standard",
        "created_at": "2025-01-01T00:00:00+00:00",
        "ows_version": "0.1.0-mock",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _derive_wallet_address(agent_id: str) -> str:
    """Derive a deterministic mock wallet address from an agent ID."""
    digest = hashlib.sha256(agent_id.encode()).hexdigest()[:40]
    return f"0x{digest}"
