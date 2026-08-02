"""Policy Resolution service — deterministic runtime stage #1.

Policy Resolution runs **before** and **independently of** the decision engine.
Given a concrete (actor, intent, target, context) tuple it:

1. Identifies the candidate published governance packages for the organization.
2. Filters them by status (``PUBLISHED``), effective date, expiration date,
   organization, jurisdiction, environment, actor type, intent type, target
   type, and asset/transaction characteristics.
3. Applies policy hierarchy and priority.
4. Detects conflicts between packages governing the same policy domain.
5. Applies explicit, deterministic conflict-resolution rules.
6. Records the exact package and requirement versions selected.
7. Produces a persistent :class:`PolicyResolution` record.

No LLM and no dynamic code execution is used anywhere in this module — every
step is deterministic. The stage never emits a decision; it only selects the
governing package versions the later stages operate on.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.governance_package import ExecutableGovernancePackage
from app.models.policy_resolution import PolicyResolution
from app.repositories.canonical import (
    ActorIdentityRepository,
    ExecutableGovernancePackageRepository,
    IntentRepository,
    OperationalContextRepository,
    PolicyResolutionRepository,
    TargetRepository,
)
from app.schemas.canonical.policy_applicability import PolicyResolutionCreate
from app.services.canonical import runtime_facts
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.canonical.errors import NotFoundError
from app.utils.canonical_enums import PackageStatus, PolicyResolutionStatus
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now

# Mapping of a package-scope key to the runtime scope fact it constrains.
_SCOPE_DIMENSIONS: dict[str, str] = {
    "jurisdictions": "jurisdiction",
    "environments": "environment",
    "actor_types": "actor_type",
    "intent_types": "intent_type",
    "target_types": "target_type",
    "asset_classes": "asset_class",
    "transaction_types": "transaction_type",
}


def _load(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _metadata(pkg: ExecutableGovernancePackage) -> dict[str, Any]:
    meta = _load(pkg.package_metadata)
    return meta if isinstance(meta, dict) else {}


def _scope(meta: dict[str, Any]) -> dict[str, Any]:
    scope = meta.get("scope")
    return scope if isinstance(scope, dict) else {}


def _priority(meta: dict[str, Any]) -> int:
    try:
        return int(meta.get("priority", 100))
    except (TypeError, ValueError):
        return 100


def _policy_domain(pkg: ExecutableGovernancePackage, meta: dict[str, Any]) -> str:
    domain = meta.get("policy_domain")
    return domain if isinstance(domain, str) and domain else pkg.package_name


def _version_key(version: Optional[str]) -> tuple[int, ...]:
    """Parse a dotted version into a tuple of ints for ordering (best effort)."""
    if not version:
        return (0,)
    parts: list[int] = []
    for chunk in str(version).split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _reference_time(context_facts: Optional[dict[str, Any]]):
    """Effective/expiration comparisons use the context timestamp if present."""
    if context_facts:
        ts = context_facts.get("context_timestamp")
        parsed = _parse_dt(ts)
        if parsed is not None:
            return parsed
    return utc_now()


def _parse_dt(value: Any):
    from datetime import datetime

    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _as_aware_pair(a, b):
    """Return ``(a, b)`` made comparable (both naive or both aware)."""
    if (a.tzinfo is None) != (b.tzinfo is None):
        return a.replace(tzinfo=None), b.replace(tzinfo=None)
    return a, b


def _passes_dates(
    pkg: ExecutableGovernancePackage, reference
) -> tuple[bool, Optional[str]]:
    """Return whether the package is within its effective/expiration window."""
    if pkg.effective_at is not None:
        eff, ref = _as_aware_pair(pkg.effective_at, reference)
        if ref < eff:
            return False, "NOT_YET_EFFECTIVE"
    if pkg.expires_at is not None:
        exp, ref = _as_aware_pair(pkg.expires_at, reference)
        if ref >= exp:
            return False, "EXPIRED"
    return True, None


def _passes_scope(
    scope: dict[str, Any], runtime_scope: dict[str, Any]
) -> tuple[bool, Optional[str]]:
    """Return whether the runtime scope satisfies every restricted dimension."""
    for scope_key, fact_key in _SCOPE_DIMENSIONS.items():
        allowed = scope.get(scope_key)
        if not allowed:
            continue  # dimension unrestricted
        if not isinstance(allowed, (list, tuple, set)):
            allowed = [allowed]
        runtime_value = runtime_scope.get(fact_key)
        if runtime_value is None or runtime_value not in allowed:
            return False, f"SCOPE_MISMATCH_{fact_key.upper()}"
    return True, None


def _selected_requirements(
    pkg: ExecutableGovernancePackage,
) -> list[dict[str, Any]]:
    requirements = _load(pkg.requirements) or []
    result: list[dict[str, Any]] = []
    for req in requirements:
        if not isinstance(req, dict):
            continue
        rid = req.get("requirement_id")
        if not rid:
            continue
        result.append(
            {
                "requirement_id": rid,
                "requirement_version": req.get("version") or pkg.package_version,
            }
        )
    return result


def resolve(db: Session, payload: PolicyResolutionCreate) -> PolicyResolution:
    """Run the deterministic policy-resolution stage and persist the record."""
    org = payload.organization_id

    actor = ActorIdentityRepository(db).get(org, payload.actor_identity_id)
    if actor is None:
        raise NotFoundError(
            f"ActorIdentity not found: {payload.actor_identity_id}"
        )
    intent = IntentRepository(db).get(org, payload.intent_id)
    if intent is None:
        raise NotFoundError(f"Intent not found: {payload.intent_id}")

    target = None
    if payload.target_id:
        target = TargetRepository(db).get(org, payload.target_id)
        if target is None:
            raise NotFoundError(f"Target not found: {payload.target_id}")

    context = None
    if payload.operational_context_id:
        context = OperationalContextRepository(db).get(
            org, payload.operational_context_id
        )
        if context is None:
            raise NotFoundError(
                f"OperationalContext not found: {payload.operational_context_id}"
            )

    runtime_scope = runtime_facts.build_scope(
        organization_id=org,
        actor=actor,
        intent=intent,
        target=target,
        context=context,
    )
    context_facts = (
        runtime_facts.build_context_facts(context) if context is not None else None
    )
    reference = _reference_time(context_facts)

    # --- 1. Candidate packages for the organization (PUBLISHED only) ---
    published = ExecutableGovernancePackageRepository(db).list_filtered(
        org, status=PackageStatus.PUBLISHED.value, limit=1000
    )

    # --- 2. Filter by dates + scope ---
    candidates: list[ExecutableGovernancePackage] = []
    for pkg in published:
        ok_dates, _ = _passes_dates(pkg, reference)
        if not ok_dates:
            continue
        meta = _metadata(pkg)
        ok_scope, _ = _passes_scope(_scope(meta), runtime_scope)
        if not ok_scope:
            continue
        candidates.append(pkg)

    candidate_ids = sorted(pkg.id for pkg in candidates)

    # --- 3./4./5. Hierarchy, priority, conflict detection + resolution ---
    domains: dict[str, list[ExecutableGovernancePackage]] = {}
    for pkg in candidates:
        meta = _metadata(pkg)
        domains.setdefault(_policy_domain(pkg, meta), []).append(pkg)

    selected_packages: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for domain in sorted(domains):
        group = domains[domain]
        ordered = sorted(group, key=lambda p: _resolution_sort_key(p))
        winner = ordered[0]

        if len(group) > 1:
            conflicts.append(
                {
                    "policy_domain": domain,
                    "competing_package_ids": sorted(p.id for p in group),
                    "winner_package_id": winner.id,
                    "strategy": "PRIORITY_THEN_SPECIFICITY_THEN_VERSION",
                    "declared_rules": _declared_conflict_rules(group),
                    "reason_code": "CONFLICT_RESOLVED_BY_PRIORITY",
                }
            )

        meta = _metadata(winner)
        selected_packages.append(
            {
                "package_id": winner.id,
                "package_name": winner.package_name,
                "package_version": winner.package_version,
                "package_hash": winner.package_hash,
                "policy_domain": domain,
                "priority": _priority(meta),
                "requirements": _selected_requirements(winner),
            }
        )

    # --- 6./7. Status, reason codes, hashes, persistence ---
    if not selected_packages:
        status = PolicyResolutionStatus.NO_APPLICABLE_POLICY.value
        reason_codes = ["NO_APPLICABLE_POLICY"]
    elif conflicts:
        status = PolicyResolutionStatus.CONFLICT_RESOLVED.value
        reason_codes = ["POLICY_RESOLVED", "CONFLICT_RESOLVED_BY_PRIORITY"]
    else:
        status = PolicyResolutionStatus.RESOLVED.value
        reason_codes = ["POLICY_RESOLVED"]

    candidate_fingerprints = sorted(
        (
            {
                "package_id": pkg.id,
                "package_version": pkg.package_version,
                "package_hash": pkg.package_hash,
            }
            for pkg in candidates
        ),
        key=lambda entry: entry["package_id"],
    )

    input_hash = hash_dict(
        {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "organization_id": org,
            "actor_identity_id": payload.actor_identity_id,
            "intent_id": payload.intent_id,
            "target_id": payload.target_id,
            "operational_context_id": payload.operational_context_id,
            "scope": runtime_scope,
            "candidates": candidate_fingerprints,
        }
    )
    result_hash = hash_dict(
        {
            "input_hash": input_hash,
            "status": status,
            "selected_packages": selected_packages,
            "conflicts": conflicts,
            "reason_codes": reason_codes,
        }
    )

    obj = PolicyResolution(
        organization_id=org,
        actor_identity_id=payload.actor_identity_id,
        intent_id=payload.intent_id,
        target_id=payload.target_id,
        operational_context_id=payload.operational_context_id,
        status=status,
        candidate_package_ids=json.dumps(candidate_ids),
        selected_packages=json.dumps(selected_packages),
        conflicts=json.dumps(conflicts),
        selection_facts=json.dumps(runtime_scope),
        reason_codes=json.dumps(reason_codes),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=input_hash,
        result_hash=result_hash,
        resolved_at=utc_now(),
    )
    return PolicyResolutionRepository(db).add(obj)


def _resolution_sort_key(pkg: ExecutableGovernancePackage) -> tuple:
    """Deterministic winner-selection key (ascending — first entry wins).

    Order of precedence: lower priority number, more specific jurisdiction
    scope, higher version, then a stable id tiebreak.
    """
    meta = _metadata(pkg)
    scope = _scope(meta)
    specificity = 1 if scope.get("jurisdictions") else 0
    negated_version = tuple(-n for n in _version_key(pkg.package_version))
    return (
        _priority(meta),
        -specificity,
        negated_version,
        pkg.id or "",
    )


def _declared_conflict_rules(
    group: Sequence[ExecutableGovernancePackage],
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for pkg in group:
        for rule in _load(pkg.conflict_resolution_rules) or []:
            if isinstance(rule, dict):
                rules.append({"package_id": pkg.id, **rule})
    return rules


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[PolicyResolution]:
    return PolicyResolutionRepository(db).get(organization_id, resource_id)


def list_(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[PolicyResolution]:
    return PolicyResolutionRepository(db).list(
        organization_id, skip=skip, limit=limit
    )
