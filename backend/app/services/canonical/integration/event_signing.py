"""Deterministic signing / verification for outbound integration events.

Every event delivered to a sync portal is signed so a consumer can independently
verify it originated from CompliAGL and was not tampered with in transit. The
signature is computed over the deterministic hash of the *authorized projection*
actually delivered to that channel.

Security properties (mirroring
:mod:`app.services.canonical.authorization_signing`):

* **Private keys are environment-backed** — read from
  :data:`app.core.config.settings.EVENT_SIGNING_KEYS`. When no key is configured
  a single deterministic development key is derived from ``SECRET_KEY`` so events
  are *always* signed and never emitted unsigned.
* **Deterministic + dependency-free** — HMAC-SHA256 from the standard library.
* **Swappable** — the HMAC registry can be replaced by an asymmetric signer
  without changing callers.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from app.core.config import settings

# Stable id for the SECRET_KEY-derived development signing key.
_DEV_SIGNER_KEY_ID = "event-dev-secret-key"


class EventSigningError(Exception):
    """Raised when signing cannot be performed (e.g. unknown key id)."""


def _key_registry() -> dict[str, str]:
    """Return the active event signing-key registry (env-backed).

    When no explicit event keys are configured, a single deterministic
    development key is derived from the environment-backed ``SECRET_KEY``.
    Explicit keys always take precedence.
    """
    keys = dict(getattr(settings, "EVENT_SIGNING_KEYS", None) or {})
    if not keys:
        secret = getattr(settings, "SECRET_KEY", "") or ""
        derived = hashlib.sha256(
            f"compliagl-events::{secret}".encode("utf-8")
        ).hexdigest()
        keys[_DEV_SIGNER_KEY_ID] = derived
    return keys


def active_signer_key_id() -> str:
    """Return the key id used to sign newly published events."""
    configured = (
        getattr(settings, "EVENT_ACTIVE_SIGNER_KEY_ID", "") or ""
    ).strip()
    registry = _key_registry()
    if configured and configured in registry:
        return configured
    return sorted(registry)[0]


def _sign(signer_key_id: str, payload_hash: str) -> str:
    registry = _key_registry()
    secret = registry.get(signer_key_id)
    if secret is None:
        raise EventSigningError(f"unknown signer_key_id: {signer_key_id!r}")
    return hmac.new(
        secret.encode("utf-8"), payload_hash.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def sign(payload_hash: str, signer_key_id: Optional[str] = None) -> tuple[str, str]:
    """Sign ``payload_hash`` and return ``(signer_key_id, signature)``."""
    key_id = signer_key_id or active_signer_key_id()
    return key_id, _sign(key_id, payload_hash)


def verify(
    signer_key_id: Optional[str],
    payload_hash: str,
    signature: Optional[str],
) -> bool:
    """Verify an event signature. Returns True iff valid."""
    if not signer_key_id or not signature:
        return False
    registry = _key_registry()
    if signer_key_id not in registry:
        return False
    expected = _sign(signer_key_id, payload_hash)
    return hmac.compare_digest(expected, signature)
