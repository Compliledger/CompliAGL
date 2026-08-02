"""Canonical persistent policy repository.

This is the single, persistent source of truth for policies. It is backed by
the ``policies`` table (the :class:`app.models.policy.Policy` ORM model) and
replaces the deprecated in-memory ``_POLICY_STORE`` in
``app/mvp2/core/policy_engine.py``.

The repository maps the structured persistent :class:`Policy` columns onto the
canonical :class:`app.mvp2.schemas.policy.PolicyRead` domain model (with a
``rules`` dict) that the deterministic decision engine consumes. Keeping a
single ``rules`` shape means there is exactly one rule vocabulary in the system.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.mvp2.schemas.policy import PolicyRead, PolicyStatus


def _load_json_list(raw: str | None) -> list:
    """Parse a JSON array column, tolerating ``None``/invalid values."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _rules_from_policy(policy: Policy) -> dict:
    """Derive the canonical ``rules`` dict from persistent policy columns."""
    rules: dict = {}
    if policy.per_tx_limit:
        rules["max_amount"] = policy.per_tx_limit
    if policy.escalation_threshold:
        rules["escalation_threshold"] = policy.escalation_threshold
    denied = _load_json_list(policy.blocked_asset_symbols)
    if denied:
        rules["denied_currencies"] = denied
    return rules


def _to_policy_read(policy: Policy) -> PolicyRead:
    """Map a persistent :class:`Policy` row to the canonical domain model."""
    status = (
        PolicyStatus.ACTIVE
        if str(policy.status).upper() == "ACTIVE"
        else PolicyStatus.INACTIVE
    )
    return PolicyRead(
        id=UUID(str(policy.id)),
        name=policy.policy_name or policy.name or "policy",
        description=policy.description,
        policy_type=(policy.policy_type or "spend"),
        rules=_rules_from_policy(policy),
        status=status,
    )


def list_active_policies(db: Session) -> list[PolicyRead]:
    """Return every ACTIVE policy as a canonical :class:`PolicyRead`."""
    policies = db.execute(
        select(Policy).where(Policy.status == "ACTIVE")
    ).scalars().all()
    return [_to_policy_read(policy) for policy in policies]


def list_policies(db: Session) -> list[PolicyRead]:
    """Return every policy (any status) as a canonical :class:`PolicyRead`."""
    policies = db.execute(select(Policy)).scalars().all()
    return [_to_policy_read(policy) for policy in policies]
