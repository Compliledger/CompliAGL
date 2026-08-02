"""Documented signing interface for canonical AIProofs.

An **AIProof** is a signed, independently verifiable governance record. A relying
party (CompliLedger, an auditor, an external system) must be able to verify —
without trusting CompliAGL at request time — that an AIProof was issued by
CompliAGL and has not been tampered with. This module defines the signing
contract and a default deterministic implementation.

Security properties
-------------------

* **Private keys are environment-backed.** Signing secrets are read from
  :data:`app.core.config.settings.AIPROOF_SIGNING_KEYS` (populated from the
  ``AIPROOF_SIGNING_KEYS`` environment variable / secret manager). Private
  signing keys are **never** hard-coded. When no key is configured a single
  deterministic development key is derived from ``SECRET_KEY`` so AIProofs are
  always signable and never emitted unsigned in a governed flow.
* **Deterministic + dependency-free.** The default signer uses HMAC-SHA256 from
  the standard library, so the same ``aiproof_hash`` and key always yield the
  same signature and verification is a constant-time comparison.
* **Swappable.** :class:`AIProofSigner` is the interface every signer must
  satisfy; the HMAC registry can be replaced by an asymmetric (e.g. Ed25519)
  signer without changing callers, by binding a different implementation.

The signature is computed over the canonical ``aiproof_hash`` (the SHA-256 of
the RFC 8785 canonical AIProof), so a valid signature transfers integrity to the
entire proof.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional, Protocol, runtime_checkable

from app.core.config import settings

# Stable identifier for the SECRET_KEY-derived development signing key.
_DEV_SIGNER_KEY_ID = "aiproof-dev-secret-key"


class SigningError(Exception):
    """Raised when signing cannot be performed (e.g. unknown key id)."""


@runtime_checkable
class AIProofSigner(Protocol):
    """Interface every AIProof signer must satisfy."""

    def signer_key_id(self) -> str:
        """Return the key id used to sign newly generated AIProofs."""
        ...

    def sign(self, signer_key_id: str, aiproof_hash: str) -> str:
        """Return the signature of ``aiproof_hash`` for ``signer_key_id``."""
        ...

    def verify(
        self,
        signer_key_id: Optional[str],
        aiproof_hash: str,
        signature: Optional[str],
    ) -> bool:
        """Return True iff ``signature`` is valid for the hash + key id."""
        ...


def _key_registry() -> dict[str, str]:
    """Return the active AIProof signing-key registry (env-backed)."""
    keys = dict(getattr(settings, "AIPROOF_SIGNING_KEYS", None) or {})
    if not keys:
        secret = getattr(settings, "SECRET_KEY", "") or ""
        derived = hashlib.sha256(
            f"compliagl-aiproof::{secret}".encode("utf-8")
        ).hexdigest()
        keys[_DEV_SIGNER_KEY_ID] = derived
    return keys


class HmacAIProofSigner:
    """Default HMAC-SHA256 AIProof signer (standard library only)."""

    def signer_key_id(self) -> str:
        configured = (
            getattr(settings, "AIPROOF_ACTIVE_SIGNER_KEY_ID", "") or ""
        ).strip()
        registry = _key_registry()
        if configured and configured in registry:
            return configured
        return sorted(registry)[0]

    def sign(self, signer_key_id: str, aiproof_hash: str) -> str:
        registry = _key_registry()
        secret = registry.get(signer_key_id)
        if secret is None:
            raise SigningError(f"unknown signer_key_id: {signer_key_id!r}")
        return hmac.new(
            secret.encode("utf-8"),
            aiproof_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def verify(
        self,
        signer_key_id: Optional[str],
        aiproof_hash: str,
        signature: Optional[str],
    ) -> bool:
        if not signer_key_id or not signature:
            return False
        registry = _key_registry()
        if signer_key_id not in registry:
            return False
        expected = self.sign(signer_key_id, aiproof_hash)
        return hmac.compare_digest(expected, signature)


# The process-wide default signer. Swap this binding to change the signing
# implementation (e.g. to an asymmetric signer) without touching callers.
_default_signer: AIProofSigner = HmacAIProofSigner()


def get_signer() -> AIProofSigner:
    """Return the configured AIProof signer."""
    return _default_signer


def active_signer_key_id() -> str:
    """Return the key id used to sign newly generated AIProofs."""
    return get_signer().signer_key_id()


def issuer() -> str:
    """Return the logical issuer identity stamped into AIProofs."""
    return (getattr(settings, "AIPROOF_ISSUER", "") or "CompliAGL").strip()


def sign(aiproof_hash: str, signer_key_id: Optional[str] = None) -> tuple[str, str]:
    """Sign ``aiproof_hash`` and return ``(signer_key_id, signature)``."""
    signer = get_signer()
    key_id = signer_key_id or signer.signer_key_id()
    return key_id, signer.sign(key_id, aiproof_hash)


def verify(
    signer_key_id: Optional[str],
    aiproof_hash: str,
    signature: Optional[str],
) -> bool:
    """Verify an AIProof signature. Returns True iff valid."""
    return get_signer().verify(signer_key_id, aiproof_hash, signature)
