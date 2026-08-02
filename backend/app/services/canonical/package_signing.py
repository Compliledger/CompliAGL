"""Deterministic signing / signature verification for governance packages.

Signing is *optional*. A registry of shared secrets keyed by ``signer_key_id``
is read from :data:`app.core.config.settings.GOVERNANCE_SIGNING_KEYS`. When the
registry is empty, signing is considered "not configured" and packages are
accepted without a signature. When the registry is populated, any package that
declares a ``signer_key_id`` must present a valid HMAC-SHA256 signature over its
``package_hash`` — invalid signatures are rejected.

HMAC-SHA256 is used (standard library only) so the contract is deterministic and
dependency-free; the registry can be swapped for asymmetric keys later without
changing callers.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from app.core.config import settings


def _key_registry() -> dict[str, str]:
    keys = getattr(settings, "GOVERNANCE_SIGNING_KEYS", None) or {}
    return dict(keys)


def signing_configured() -> bool:
    """Return True when at least one signing key is registered."""
    return bool(_key_registry())


def compute_signature(signer_key_id: str, package_hash: str) -> str:
    """Return the HMAC-SHA256 signature of ``package_hash`` for ``signer_key_id``.

    Raises :class:`KeyError` if the key id is unknown.
    """
    secret = _key_registry()[signer_key_id]
    return hmac.new(
        secret.encode("utf-8"), package_hash.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_signature(
    signer_key_id: Optional[str], package_hash: str, signature: Optional[str]
) -> bool:
    """Verify a package signature.

    Returns True when the signature is valid, False otherwise. When signing is
    not configured and no ``signer_key_id`` is supplied, the package is treated
    as validly (un)signed and this returns True.
    """
    registry = _key_registry()

    # Signing not configured and no signer declared -> nothing to verify.
    if not registry and not signer_key_id:
        return True

    # A signer was declared but no/unknown key or missing signature -> invalid.
    if not signer_key_id or signer_key_id not in registry:
        return False
    if not signature:
        return False

    expected = compute_signature(signer_key_id, package_hash)
    return hmac.compare_digest(expected, signature)
