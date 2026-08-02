"""Documented signing interface for execution authorizations.

An :class:`ExecutionAuthorization` is a signed, first-class resource: an external
execution system must be able to **independently verify** that an authorization
was issued by CompliAGL and has not been tampered with. This module defines the
signing contract and a default deterministic implementation.

Security properties
-------------------

* **Private keys are environment-backed.** Signing secrets are read from
  :data:`app.core.config.settings.AUTHORIZATION_SIGNING_KEYS` (populated from the
  ``AUTHORIZATION_SIGNING_KEYS`` environment variable / secret manager). Private
  signing keys are **never** hard-coded in source. When no key is configured a
  single deterministic development key is derived from ``SECRET_KEY`` (also
  environment-backed) so authorizations are *always* signed and never emitted
  unsigned.
* **Deterministic + dependency-free.** The default signer uses HMAC-SHA256 from
  the standard library, so the same ``authorization_hash`` and key always yield
  the same signature and verification is a constant-time comparison.
* **Swappable.** :class:`AuthorizationSigner` is the interface every signer must
  satisfy; the HMAC registry can be replaced by an asymmetric (e.g. Ed25519)
  signer without changing callers, by binding a different implementation.

The signature is computed over the deterministic ``authorization_hash`` that
binds every immutable authorization field (decision hash, actor/intent/target,
amount caps, nonce, expiry, ...), so a signature transfers integrity to the whole
authorization.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional, Protocol, runtime_checkable

from app.core.config import settings

# Stable identifier for the SECRET_KEY-derived development signing key. Using a
# named id keeps verification working across restarts without extra config.
_DEV_SIGNER_KEY_ID = "authz-dev-secret-key"


class SigningError(Exception):
    """Raised when signing cannot be performed (e.g. unknown key id)."""


@runtime_checkable
class AuthorizationSigner(Protocol):
    """Interface every authorization signer must satisfy."""

    def signer_key_id(self) -> str:
        """Return the key id used to sign newly issued authorizations."""
        ...

    def sign(self, signer_key_id: str, authorization_hash: str) -> str:
        """Return the signature of ``authorization_hash`` for ``signer_key_id``."""
        ...

    def verify(
        self,
        signer_key_id: Optional[str],
        authorization_hash: str,
        signature: Optional[str],
    ) -> bool:
        """Return True iff ``signature`` is valid for the hash + key id."""
        ...


def _key_registry() -> dict[str, str]:
    """Return the active signing-key registry (env-backed).

    When no explicit authorization keys are configured, a single deterministic
    development key is derived from the (environment-backed) ``SECRET_KEY`` so
    authorizations are always signed. Explicit keys always take precedence.
    """
    keys = dict(getattr(settings, "AUTHORIZATION_SIGNING_KEYS", None) or {})
    if not keys:
        secret = getattr(settings, "SECRET_KEY", "") or ""
        derived = hashlib.sha256(
            f"compliagl-authz::{secret}".encode("utf-8")
        ).hexdigest()
        keys[_DEV_SIGNER_KEY_ID] = derived
    return keys


class HmacAuthorizationSigner:
    """Default HMAC-SHA256 authorization signer (standard library only)."""

    def signer_key_id(self) -> str:
        configured = (
            getattr(settings, "AUTHORIZATION_ACTIVE_SIGNER_KEY_ID", "") or ""
        ).strip()
        registry = _key_registry()
        if configured and configured in registry:
            return configured
        # Deterministic default: the first key id in sorted order.
        return sorted(registry)[0]

    def sign(self, signer_key_id: str, authorization_hash: str) -> str:
        registry = _key_registry()
        secret = registry.get(signer_key_id)
        if secret is None:
            raise SigningError(f"unknown signer_key_id: {signer_key_id!r}")
        return hmac.new(
            secret.encode("utf-8"),
            authorization_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def verify(
        self,
        signer_key_id: Optional[str],
        authorization_hash: str,
        signature: Optional[str],
    ) -> bool:
        if not signer_key_id or not signature:
            return False
        registry = _key_registry()
        if signer_key_id not in registry:
            return False
        expected = self.sign(signer_key_id, authorization_hash)
        return hmac.compare_digest(expected, signature)


# The process-wide default signer. Swap this binding to change the signing
# implementation (e.g. to an asymmetric signer) without touching callers.
_default_signer: AuthorizationSigner = HmacAuthorizationSigner()


def get_signer() -> AuthorizationSigner:
    """Return the configured authorization signer."""
    return _default_signer


def active_signer_key_id() -> str:
    """Return the key id used to sign newly issued authorizations."""
    return get_signer().signer_key_id()


def sign(authorization_hash: str, signer_key_id: Optional[str] = None) -> tuple[str, str]:
    """Sign ``authorization_hash`` and return ``(signer_key_id, signature)``."""
    signer = get_signer()
    key_id = signer_key_id or signer.signer_key_id()
    return key_id, signer.sign(key_id, authorization_hash)


def verify(
    signer_key_id: Optional[str],
    authorization_hash: str,
    signature: Optional[str],
) -> bool:
    """Verify an authorization signature. Returns True iff valid."""
    return get_signer().verify(signer_key_id, authorization_hash, signature)
