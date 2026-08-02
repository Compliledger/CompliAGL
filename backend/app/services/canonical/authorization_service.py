"""Execution Authorization service — signed, first-class authorization gate.

Only an ``APPROVED`` :class:`Decision` may create an
:class:`ExecutionAuthorization`. An authorization is a **signed, first-class
resource**: it is narrowly bound to a single actor/intent/target/action, carries
the decision/assessment/evidence/policy hashes it was derived from, and is signed
so an external execution system can **independently verify** it before acting.

Security properties enforced here:

* **No authorization for DENIED / ESCALATED decisions.**
* **Replay protection** — one-time-use authorizations carry a random ``nonce``
  and can only be consumed once; a consumed/expired/revoked authorization is
  rejected.
* **Idempotency** — issuing with a repeated ``idempotency_key`` returns the
  original authorization instead of minting a new one.
* **Bound-field verification** — :func:`verify` recomputes the authorization
  hash, checks the signature, lifecycle status and expiry, and (optionally)
  checks caller-supplied bound fields (target, amount, decision hash, ...) so a
  modified execution request is rejected before acceptance.
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import timedelta
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.execution_authorization import ExecutionAuthorization
from app.repositories.canonical import (
    DecisionRepository,
    ExecutionAuthorizationRepository,
    IntentRepository,
    PolicyResolutionRepository,
)
from app.services.canonical import authorization_signing
from app.services.canonical.errors import ConflictError, NotFoundError
from app.utils.canonical_enums import AuthorizationStatus, DecisionOutcome
from app.utils.hashing import hash_dict
from app.utils.timestamps import ensure_aware, utc_now

# Lifecycle states from which an authorization is still usable.
_LIVE_STATES = {
    AuthorizationStatus.ISSUED.value,
    AuthorizationStatus.ACTIVE.value,
}


def _load(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _compute_authorization_hash(fields: dict[str, Any]) -> str:
    """Deterministic hash binding every immutable authorization field."""
    return hash_dict(fields)


def _bound_fields(auth: ExecutionAuthorization) -> dict[str, Any]:
    """The immutable fields the authorization hash + signature bind."""
    return {
        "authorization_id": auth.id,
        "organization_id": auth.organization_id,
        "decision_id": auth.decision_id,
        "actor_id": auth.actor_id,
        "intent_id": auth.intent_id,
        "target_id": auth.target_id,
        "authorized_action": auth.authorized_action,
        "authorized_parameter_constraints": _load(
            auth.authorized_parameter_constraints
        ),
        "max_amount_minor": auth.max_amount_minor,
        "max_amount_currency": auth.max_amount_currency,
        "permitted_execution_system": auth.permitted_execution_system,
        "one_time_use": auth.one_time_use,
        "nonce": auth.nonce,
        "issued_at": (
            ensure_aware(auth.issued_at).isoformat() if auth.issued_at else None
        ),
        "expires_at": (
            ensure_aware(auth.expires_at).isoformat() if auth.expires_at else None
        ),
        "policy_package_hash": auth.policy_package_hash,
        "assessment_hash": auth.assessment_hash,
        "evidence_package_hash": auth.evidence_package_hash,
        "decision_hash": auth.decision_hash,
    }


def _is_expired(auth: ExecutionAuthorization, now=None) -> bool:
    if auth.expires_at is None:
        return False
    now = now or utc_now()
    return ensure_aware(now) >= ensure_aware(auth.expires_at)


def _expire_if_needed(
    db: Session, auth: ExecutionAuthorization
) -> ExecutionAuthorization:
    """Mark a live-but-expired authorization EXPIRED and persist."""
    if auth.status in _LIVE_STATES and _is_expired(auth):
        auth.status = AuthorizationStatus.EXPIRED.value
        ExecutionAuthorizationRepository(db).save(auth)
    return auth


# --------------------------------------------------------------------------- #
# Issue
# --------------------------------------------------------------------------- #
def issue(
    db: Session,
    organization_id: str,
    decision_id: str,
    *,
    permitted_execution_system: Optional[str] = None,
    authorized_parameter_constraints: Optional[dict[str, Any]] = None,
    max_amount_minor: Optional[int] = None,
    max_amount_currency: Optional[str] = None,
    expires_at=None,
    idempotency_key: Optional[str] = None,
    one_time_use: bool = True,
) -> ExecutionAuthorization:
    """Issue a signed authorization for an APPROVED decision.

    Raises :class:`ConflictError` if the decision is not ``APPROVED``.
    """
    org = organization_id
    repo = ExecutionAuthorizationRepository(db)

    # Idempotency: a repeated key returns the original result.
    if idempotency_key:
        existing = repo.get_by_idempotency_key(org, idempotency_key)
        if existing is not None:
            return existing

    decision = DecisionRepository(db).get(org, decision_id)
    if decision is None:
        raise NotFoundError(f"Decision not found: {decision_id}")

    if decision.outcome != DecisionOutcome.APPROVED.value:
        raise ConflictError(
            "Execution authorization can only be issued for an APPROVED "
            f"decision (decision {decision_id} is {decision.outcome})."
        )

    intent = IntentRepository(db).get(org, decision.intent_id)
    if intent is None:
        raise NotFoundError(f"Intent not found: {decision.intent_id}")

    target_id = None
    if decision.policy_resolution_id:
        resolution = PolicyResolutionRepository(db).get(
            org, decision.policy_resolution_id
        )
        if resolution is not None:
            target_id = resolution.target_id

    now = utc_now()
    if expires_at is None:
        ttl = int(getattr(settings, "AUTHORIZATION_DEFAULT_TTL_SECONDS", 900) or 900)
        expires_at = now + timedelta(seconds=ttl)

    # Narrow binding: default amount cap to the intent's requested amount.
    if max_amount_minor is None:
        max_amount_minor = intent.amount_minor
    if max_amount_currency is None:
        max_amount_currency = intent.amount_currency

    auth = ExecutionAuthorization(
        id=str(uuid.uuid4()),
        organization_id=org,
        decision_id=decision_id,
        intent_id=intent.id,
        actor_id=intent.actor_id,
        target_id=target_id,
        status=AuthorizationStatus.ISSUED.value,
        authorized_action=intent.action,
        authorized_parameter_constraints=(
            json.dumps(authorized_parameter_constraints)
            if authorized_parameter_constraints is not None
            else None
        ),
        constraints=(
            json.dumps(authorized_parameter_constraints)
            if authorized_parameter_constraints is not None
            else None
        ),
        max_amount_minor=max_amount_minor,
        max_amount_currency=max_amount_currency,
        permitted_execution_system=permitted_execution_system,
        one_time_use=one_time_use,
        nonce=secrets.token_hex(16),
        idempotency_key=idempotency_key,
        issued_at=now,
        authorized_at=now,
        expires_at=expires_at,
        policy_package_hash=decision.policy_package_hash,
        assessment_hash=decision.assessment_hash,
        evidence_package_hash=decision.evidence_package_hash,
        decision_hash=decision.decision_hash,
    )
    # A stable token external systems can present; distinct from the nonce.
    auth.authorization_token = uuid.uuid4().hex

    # Bind + sign.
    auth.authorization_hash = _compute_authorization_hash(_bound_fields(auth))
    signer_key_id, signature = authorization_signing.sign(auth.authorization_hash)
    auth.signer_key_id = signer_key_id
    auth.signature = signature

    return repo.add(auth)


# --------------------------------------------------------------------------- #
# Verify
# --------------------------------------------------------------------------- #
def verify(
    db: Session,
    organization_id: str,
    authorization_id: str,
    *,
    expected_fields: Optional[dict[str, Any]] = None,
    activate: bool = True,
) -> Optional[dict[str, Any]]:
    """Independently verify an authorization before execution acceptance.

    Recomputes the authorization hash, checks the signature, lifecycle status and
    expiry, and (when ``expected_fields`` is supplied) verifies every bound field
    the caller intends to execute against. Returns ``None`` if the authorization
    does not exist, otherwise a result dict ``{valid, reasons, status, ...}``.

    On the first successful verification a live authorization is activated
    (``ISSUED -> ACTIVE``) when ``activate`` is true.
    """
    repo = ExecutionAuthorizationRepository(db)
    auth = repo.get(organization_id, authorization_id)
    if auth is None:
        return None

    auth = _expire_if_needed(db, auth)

    reasons: list[str] = []

    # 1. Signature + hash integrity (independent of DB trust).
    recomputed = _compute_authorization_hash(_bound_fields(auth))
    hash_ok = recomputed == auth.authorization_hash
    if not hash_ok:
        reasons.append("AUTHORIZATION_HASH_MISMATCH")
    signature_ok = authorization_signing.verify(
        auth.signer_key_id, auth.authorization_hash, auth.signature
    )
    if not signature_ok:
        reasons.append("INVALID_SIGNATURE")

    # 2. Lifecycle status.
    if auth.status == AuthorizationStatus.REVOKED.value:
        reasons.append("AUTHORIZATION_REVOKED")
    elif auth.status == AuthorizationStatus.CONSUMED.value:
        reasons.append("AUTHORIZATION_ALREADY_CONSUMED")
    elif auth.status == AuthorizationStatus.EXPIRED.value:
        reasons.append("AUTHORIZATION_EXPIRED")
    elif auth.status not in _LIVE_STATES:
        reasons.append("AUTHORIZATION_NOT_LIVE")

    if _is_expired(auth):
        if "AUTHORIZATION_EXPIRED" not in reasons:
            reasons.append("AUTHORIZATION_EXPIRED")

    # 3. Bound-field verification (reject a modified execution request).
    mismatched: list[str] = []
    if expected_fields:
        bound = _bound_fields(auth)
        for key, value in expected_fields.items():
            if bound.get(key) != value:
                mismatched.append(key)
        if mismatched:
            reasons.append("BOUND_FIELD_MISMATCH")

    valid = not reasons

    if valid and activate and auth.status == AuthorizationStatus.ISSUED.value:
        auth.status = AuthorizationStatus.ACTIVE.value
        repo.save(auth)

    result = {
        "authorization_id": auth.id,
        "valid": valid,
        "status": auth.status,
        "reasons": reasons,
        "hash_valid": hash_ok,
        "signature_valid": signature_ok,
        "expired": _is_expired(auth),
    }
    if mismatched:
        result["mismatched_fields"] = mismatched
    return result


# --------------------------------------------------------------------------- #
# Consume (one-time-use + replay protection)
# --------------------------------------------------------------------------- #
def consume(
    db: Session, organization_id: str, authorization_id: str
) -> ExecutionAuthorization:
    """Consume a one-time-use authorization.

    Raises :class:`NotFoundError` if it does not exist and :class:`ConflictError`
    when it is not in a live, non-expired state (replay / reuse protection).
    """
    repo = ExecutionAuthorizationRepository(db)
    auth = repo.get(organization_id, authorization_id)
    if auth is None:
        raise NotFoundError(
            f"ExecutionAuthorization not found: {authorization_id}"
        )

    auth = _expire_if_needed(db, auth)

    if auth.status == AuthorizationStatus.CONSUMED.value:
        raise ConflictError(
            "Authorization already consumed (replay rejected): "
            f"{authorization_id}"
        )
    if auth.status == AuthorizationStatus.REVOKED.value:
        raise ConflictError(f"Authorization revoked: {authorization_id}")
    if auth.status == AuthorizationStatus.EXPIRED.value or _is_expired(auth):
        raise ConflictError(f"Authorization expired: {authorization_id}")
    if auth.status not in _LIVE_STATES:
        raise ConflictError(
            f"Authorization not consumable in status {auth.status}: "
            f"{authorization_id}"
        )

    # Signature must still be valid before consumption is accepted.
    if not authorization_signing.verify(
        auth.signer_key_id, auth.authorization_hash, auth.signature
    ):
        raise ConflictError(
            f"Authorization signature invalid: {authorization_id}"
        )

    auth.status = AuthorizationStatus.CONSUMED.value
    auth.consumed_at = utc_now()
    return repo.save(auth)


# --------------------------------------------------------------------------- #
# Revoke
# --------------------------------------------------------------------------- #
def revoke(
    db: Session,
    organization_id: str,
    authorization_id: str,
    *,
    reason: Optional[str] = None,
) -> ExecutionAuthorization:
    """Revoke a live authorization."""
    repo = ExecutionAuthorizationRepository(db)
    auth = repo.get(organization_id, authorization_id)
    if auth is None:
        raise NotFoundError(
            f"ExecutionAuthorization not found: {authorization_id}"
        )
    if auth.status == AuthorizationStatus.CONSUMED.value:
        raise ConflictError(
            f"Cannot revoke a consumed authorization: {authorization_id}"
        )
    if auth.status == AuthorizationStatus.REVOKED.value:
        return auth
    auth.status = AuthorizationStatus.REVOKED.value
    auth.revoked_at = utc_now()
    auth.revocation_reason = reason
    return repo.save(auth)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[ExecutionAuthorization]:
    return ExecutionAuthorizationRepository(db).get(organization_id, resource_id)


def list_(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[ExecutionAuthorization]:
    return ExecutionAuthorizationRepository(db).list(
        organization_id, skip=skip, limit=limit
    )
