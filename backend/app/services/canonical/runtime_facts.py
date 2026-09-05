"""Assemble deterministic runtime facts from the canonical input objects.

Both the Policy Resolution and Applicability Evaluation stages operate on a
*flat, deterministic* view of the runtime inputs (ActorIdentity, Intent,
Target, OperationalContext). This module builds that view once so both stages —
and the deterministic hashes they produce — see exactly the same facts.

A **missing** target or operational context is represented by the *absence* of
the corresponding top-level key. Expressions that reference a missing fact
therefore evaluate to ``INDETERMINATE`` rather than silently to ``False`` —
missing context can never silently produce approval.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.models.actor_identity import ActorIdentity
from app.models.intent import Intent
from app.models.operational_context import OperationalContext
from app.models.target import Target
from app.services.canonical.authority_context_service import AuthorityContext


def _load(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def build_actor_facts(actor: ActorIdentity) -> dict[str, Any]:
    return {
        "id": actor.id,
        "actor_type": actor.actor_type,
        "human_principal_id": actor.human_principal_id,
        "external_account_id": actor.external_account_id,
        "wallet_or_agent_account_id": actor.wallet_or_agent_account_id,
        "credential_type": actor.credential_type,
        "verification_status": actor.verification_status,
        "revocation_status": actor.revocation_status,
        "metadata": _load(actor.identity_metadata) or {},
    }


def build_intent_facts(intent: Intent) -> dict[str, Any]:
    return {
        "id": intent.id,
        "intent_type": intent.intent_type,
        "action": intent.action,
        "requested_outcome": intent.requested_outcome,
        "originating_application": intent.originating_application,
        "amount_minor": intent.amount_minor,
        "amount_currency": intent.amount_currency,
        "parameters": _load(intent.parameters) or {},
        "status": intent.status,
    }


def build_target_facts(target: Target) -> dict[str, Any]:
    return {
        "id": target.id,
        "target_type": target.target_type,
        "external_identifier": target.external_identifier,
        "owner": target.owner,
        "organization": target.organization,
        "classification": target.classification,
        "trust_status": target.trust_status,
        "network_or_environment": target.network_or_environment,
        "metadata": _load(target.target_metadata) or {},
    }


def build_context_facts(context: OperationalContext) -> dict[str, Any]:
    return {
        "id": context.id,
        "business_unit": context.business_unit,
        "jurisdiction": context.jurisdiction,
        "environment": context.environment,
        "context_timestamp": _iso(context.context_timestamp),
        "risk_state": _load(context.risk_state) or {},
        "account_state": _load(context.account_state) or {},
        "allowance_state": _load(context.allowance_state) or {},
        "merchant_state": _load(context.merchant_state) or {},
        "asset_state": _load(context.asset_state) or {},
        "network_state": _load(context.network_state) or {},
        "operational_state_snapshot": _load(context.operational_state_snapshot)
        or {},
    }


def build_authority_facts(authority: AuthorityContext) -> dict[str, Any]:
    return {
        "status": authority.status,
        "reason": authority.reason,
        "sufficient": authority.sufficient,
        "active": authority.active,
        "current_trust_state": authority.current_trust_state,
        "authority_revision": authority.authority_revision,
    }


def build_facts(
    *,
    actor: ActorIdentity,
    intent: Intent,
    target: Optional[Target],
    context: Optional[OperationalContext],
    authority: Optional[AuthorityContext] = None,
) -> dict[str, Any]:
    """Build the nested runtime-facts mapping for the governed tuple.

    ``target`` / ``context`` keys are omitted entirely when the corresponding
    input is absent, so references to them evaluate to ``INDETERMINATE`` --
    both are legitimately optional depending on intent type.

    ``authority`` follows the same omit-when-absent rule, but for a different
    reason: it is only ever provided at all when the governing package
    declared ``requires_authority_context: true`` (see decision_service.py).
    Packages that don't declare it never see an ``authority`` key, so they
    behave exactly as they did before this integration existed. Packages
    that *do* declare it always get the key -- even when the underlying
    CompliIdentity call failed (``authority.status == "UNAVAILABLE"``) -- so
    package-authored conditions can inspect it if they choose to, though the
    engine-level fail-closed guard in ``decision_service._resolve_outcome``
    does not depend on them doing so.
    """
    facts: dict[str, Any] = {
        "actor": build_actor_facts(actor),
        "intent": build_intent_facts(intent),
    }
    if target is not None:
        facts["target"] = build_target_facts(target)
    if context is not None:
        facts["context"] = build_context_facts(context)
    if authority is not None:
        facts["authority"] = build_authority_facts(authority)
    return facts


def build_scope(
    *,
    organization_id: str,
    actor: ActorIdentity,
    intent: Intent,
    target: Optional[Target],
    context: Optional[OperationalContext],
) -> dict[str, Any]:
    """Derive the flat scope facts used to filter candidate packages.

    Values are ``None`` when the corresponding input (target/context) or field
    is absent. A ``None`` scope value never matches a package that *restricts*
    that dimension.
    """
    intent_params = _load(intent.parameters) or {}
    asset_class = None
    transaction_type = intent_params.get("transaction_type") or intent.action
    if target is not None:
        asset_class = target.classification
    if asset_class is None:
        asset_class = intent_params.get("asset_class")
    return {
        "organization_id": organization_id,
        "jurisdiction": context.jurisdiction if context is not None else None,
        "environment": context.environment if context is not None else None,
        "actor_type": actor.actor_type,
        "intent_type": intent.intent_type,
        "target_type": target.target_type if target is not None else None,
        "asset_class": asset_class,
        "transaction_type": transaction_type,
    }
