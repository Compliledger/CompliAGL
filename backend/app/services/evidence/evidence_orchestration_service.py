"""Evidence orchestration — build a plan and collect evidence via connectors.

This is the heart of the evidence layer. Given a completed policy resolution it:

1. builds an :class:`~app.models.evidence_orchestration_plan.EvidenceOrchestrationPlan`
   from the resolved :class:`~app.models.evidence_requirement_set.EvidenceRequirementSet`,
2. selects the single **authoritative** connector for each requirement (by
   source type + supported evidence type), marking requirements with no
   connector explicitly ``UNRESOLVED`` (never silently satisfied),
3. collects evidence **in parallel where safe** (connector calls are pure and
   run in a thread pool; all database writes happen sequentially),
4. applies each connector's **retry policy** and **timeout** behavior,
5. records full **provenance** for every item,
6. records **collection failures** explicitly,
7. **never** fabricates evidence — a source with nothing to return yields a
   ``NOT_FOUND`` item with no payload,
8. **never** uses a mock connector silently in production mode — mock
   connectors are rejected with an explicit ``REJECTED_MOCK`` status,
9. marks unresolved evidence explicitly on the plan and the job.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.evidence_collection_job import EvidenceCollectionJob
from app.models.evidence_orchestration_plan import EvidenceOrchestrationPlan
from app.models.raw_evidence import RawEvidence
from app.repositories.canonical import (
    EvidenceCollectionJobRepository,
    EvidenceOrchestrationPlanRepository,
    EvidenceRequirementSetRepository,
    OperationalContextRepository,
    PolicyResolutionRepository,
    RawEvidenceRepository,
    TargetRepository,
)
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.evidence.connectors.base import (
    CollectRequest,
    CollectResult,
    ConnectorError,
    ConnectorTimeout,
    EvidenceConnector,
)
from app.services.evidence.connectors import ConnectorRegistry
from app.utils.canonical_enums import (
    EnvironmentType,
    EvidenceCollectionStatus,
    EvidenceSourceType,
    RequiredEvidenceState,
    SensitivityClassification,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now

# Evidence requirement states that require an actual collection attempt.
_COLLECTIBLE_STATES = {
    RequiredEvidenceState.REQUIRED.value,
    RequiredEvidenceState.CONDITIONAL.value,
    RequiredEvidenceState.OPTIONAL.value,
}

# Free-form authoritative source types (as authored in governance packages)
# mapped onto the generic, platform-neutral source types.
_SOURCE_TYPE_ALIASES: dict[str, str] = {
    "governance_registry": EvidenceSourceType.GOVERNANCE_REGISTRY.value,
    "compliledger": EvidenceSourceType.GOVERNANCE_REGISTRY.value,
    "policy_registry": EvidenceSourceType.GOVERNANCE_REGISTRY.value,
    "identity_provider": EvidenceSourceType.IDENTITY_PROVIDER.value,
    "identity": EvidenceSourceType.IDENTITY_PROVIDER.value,
    "delegation_source": EvidenceSourceType.IDENTITY_PROVIDER.value,
    "external_application": EvidenceSourceType.EXTERNAL_APPLICATION.value,
    "external_api": EvidenceSourceType.EXTERNAL_APPLICATION.value,
    "merchant": EvidenceSourceType.EXTERNAL_APPLICATION.value,
    "procurement_system": EvidenceSourceType.EXTERNAL_APPLICATION.value,
    "application": EvidenceSourceType.EXTERNAL_APPLICATION.value,
    "account_state": EvidenceSourceType.ACCOUNT_STATE.value,
    "wallet": EvidenceSourceType.ACCOUNT_STATE.value,
    "account": EvidenceSourceType.ACCOUNT_STATE.value,
    "allowance_source": EvidenceSourceType.ACCOUNT_STATE.value,
    "ledger": EvidenceSourceType.ACCOUNT_STATE.value,
    "approval_workflow": EvidenceSourceType.APPROVAL_WORKFLOW.value,
    "approval_source": EvidenceSourceType.APPROVAL_WORKFLOW.value,
    "approval": EvidenceSourceType.APPROVAL_WORKFLOW.value,
    "compliance_officer": EvidenceSourceType.APPROVAL_WORKFLOW.value,
    "execution_result": EvidenceSourceType.EXECUTION_RESULT.value,
    "execution_source": EvidenceSourceType.EXECUTION_RESULT.value,
    "settlement": EvidenceSourceType.EXECUTION_RESULT.value,
}

# Sensitivity classes whose payloads must never be stored inline in the runtime.
_SECURE_SENSITIVITIES = {
    SensitivityClassification.PII.value,
    SensitivityClassification.SENSITIVE.value,
    SensitivityClassification.SECRET.value,
}


def _load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def _map_source_type(declared: Optional[str]) -> Optional[str]:
    """Map a package-declared source type onto a generic source type."""
    if not declared:
        return None
    # Already a generic value?
    if declared in {t.value for t in EvidenceSourceType}:
        return declared
    return _SOURCE_TYPE_ALIASES.get(declared.strip().lower())


def _resolve_binding(
    token: Optional[str],
    *,
    actor_id: Optional[str],
    target_id: Optional[str],
    intent_id: Optional[str],
) -> Optional[str]:
    """Resolve a binding token (actor/target/intent) to a concrete runtime id.

    ``target_id`` here is the value the ``"target"`` token resolves to — the
    caller passes the ``Target.external_identifier`` (the identifier
    namespace external systems/connectors actually report evidence against),
    not CompliAGL's internal ``Target.id`` primary key.
    """
    if not token:
        return None
    key = token.strip().lower()
    if key == "actor":
        return actor_id
    if key == "target":
        return target_id
    if key in ("intent", "transaction"):
        return intent_id
    return None


# --------------------------------------------------------------------------- #
# Plan building
# --------------------------------------------------------------------------- #
def build_plan(
    db: Session,
    organization_id: str,
    evidence_set,
    registry: ConnectorRegistry,
    *,
    production_mode: bool,
) -> EvidenceOrchestrationPlan:
    """Build and persist the orchestration plan for an evidence requirement set."""
    actor_id = evidence_set.actor_identity_id
    target_id = evidence_set.target_id
    intent_id = evidence_set.intent_id

    # The "target" binding token resolves to the Target's own
    # external_identifier -- the namespace external connectors actually
    # report evidence against -- not CompliAGL's internal Target.id primary
    # key. `target_id` (the internal PK) is retained above for the plan's
    # own FK-style linkage (see EvidenceOrchestrationPlan.target_id below).
    target_external_id: Optional[str] = None
    if target_id is not None:
        target = TargetRepository(db).get(organization_id, target_id)
        target_external_id = target.external_identifier if target else None

    requirements = _load(evidence_set.evidence_requirements, []) or []
    tasks: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for req in requirements:
        if not isinstance(req, dict):
            continue
        state = req.get("state")
        req_id = req.get("evidence_requirement_id")
        evidence_type = req.get("evidence_type")

        if state == RequiredEvidenceState.UNRESOLVED.value:
            unresolved.append(
                {
                    "evidence_requirement_id": req_id,
                    "evidence_type": evidence_type,
                    "reason": "UPSTREAM_UNRESOLVED_REQUIREMENT",
                }
            )
            continue
        if state not in _COLLECTIBLE_STATES:
            continue

        declared_source = req.get("allowed_source_type")
        generic_source = _map_source_type(declared_source)
        if generic_source is not None:
            connector = registry.select_authoritative(
                generic_source, evidence_type
            )
        else:
            connector = registry.select_authoritative(None, evidence_type)

        if connector is None:
            unresolved.append(
                {
                    "evidence_requirement_id": req_id,
                    "evidence_type": evidence_type,
                    "declared_source_type": declared_source,
                    "required_source_type": generic_source,
                    "reason": "NO_AUTHORITATIVE_CONNECTOR",
                }
            )
            continue

        subject_id = _resolve_binding(
            req.get("subject"),
            actor_id=actor_id,
            target_id=target_external_id,
            intent_id=intent_id,
        )
        resolved_target_id = _resolve_binding(
            req.get("target"),
            actor_id=actor_id,
            target_id=target_external_id,
            intent_id=intent_id,
        )

        tasks.append(
            {
                "evidence_requirement_id": req_id,
                "evidence_type": evidence_type,
                "declared_source_type": declared_source,
                "required_source_type": generic_source
                or connector.source_type,
                "connector_id": connector.connector_id,
                "source_id": connector.connector_id,
                "source_type": connector.source_type,
                "is_mock": bool(connector.is_mock),
                "subject_binding": req.get("subject"),
                "target_binding": req.get("target"),
                "subject_id": subject_id,
                "target_id": resolved_target_id,
                "intent_id": intent_id,
                "allowed_issuers": list(req.get("allowed_issuers") or []),
                "freshness_threshold": req.get("freshness_threshold"),
                "mandatory": bool(req.get("mandatory", True)),
                "state": state,
                "timeout_seconds": float(connector.timeout_seconds),
                "retry_policy": connector.retry_policy.as_dict(),
            }
        )

    tasks.sort(key=lambda t: (t["evidence_requirement_id"] or ""))
    unresolved.sort(key=lambda u: (u["evidence_requirement_id"] or ""))

    reason_codes = ["EVIDENCE_PLAN_BUILT"]
    if unresolved:
        reason_codes.append("EVIDENCE_PLAN_HAS_UNRESOLVED")
    if not tasks:
        reason_codes.append("EVIDENCE_PLAN_NO_TASKS")

    plan_hash = hash_dict(
        {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "evidence_requirement_set_id": evidence_set.id,
            "evidence_requirement_set_result_hash": evidence_set.result_hash,
            "production_mode": production_mode,
            "tasks": [
                {k: t[k] for k in sorted(t) if k not in ("timeout_seconds",)}
                for t in tasks
            ],
            "unresolved": unresolved,
        }
    )

    plan = EvidenceOrchestrationPlan(
        organization_id=organization_id,
        policy_resolution_id=evidence_set.policy_resolution_id,
        evidence_requirement_set_id=evidence_set.id,
        actor_identity_id=actor_id,
        intent_id=intent_id,
        target_id=target_id,
        operational_context_id=evidence_set.operational_context_id,
        production_mode="true" if production_mode else "false",
        tasks=json.dumps(tasks),
        unresolved=json.dumps(unresolved),
        reason_codes=json.dumps(reason_codes),
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        plan_hash=plan_hash,
        planned_at=utc_now(),
    )
    return EvidenceOrchestrationPlanRepository(db).add(plan)


# --------------------------------------------------------------------------- #
# Collection execution
# --------------------------------------------------------------------------- #
def _collect_with_retries(
    connector: EvidenceConnector, request: CollectRequest
) -> tuple[CollectResult, int]:
    """Collect one item, applying the connector's retry policy and timeout.

    Returns ``(result, attempts)``. Timeouts and errors are retried up to
    ``retry_policy.max_attempts``; the final failure is returned as a
    :class:`CollectResult` with an explicit ``TIMEOUT``/``FAILED`` status so the
    orchestrator can record it (evidence is never fabricated to hide a failure).
    """
    policy = connector.retry_policy
    attempts = 0
    last_error: Optional[str] = None
    status = EvidenceCollectionStatus.FAILED.value
    for _ in range(max(1, policy.max_attempts)):
        attempts += 1
        try:
            return connector.collect(request), attempts
        except ConnectorTimeout as exc:
            last_error = str(exc)
            status = EvidenceCollectionStatus.TIMEOUT.value
            if not policy.retry_on_timeout:
                break
        except ConnectorError as exc:
            last_error = str(exc)
            status = EvidenceCollectionStatus.FAILED.value
    return (
        CollectResult(status=status, payload=None, error=last_error),
        attempts,
    )


def _persist_raw_evidence(
    db: Session,
    *,
    organization_id: str,
    job: EvidenceCollectionJob,
    task: dict[str, Any],
    connector: EvidenceConnector,
    result: CollectResult,
    attempts: int,
) -> RawEvidence:
    """Persist a single collected/failed item with full provenance."""
    collected_at = utc_now()

    # Compute the payload hash over the connector payload (if any) before we
    # decide whether to hold it inline or by secure reference.
    payload_hash: Optional[str] = None
    stored_payload: Optional[str] = None
    payload_reference: Optional[str] = result.payload_reference
    sensitivity = result.sensitivity

    if result.payload is not None:
        payload_hash = hash_dict({"payload": result.payload})
        if sensitivity in _SECURE_SENSITIVITIES:
            # Sensitive payloads are never stored inline in the runtime; only a
            # secure reference and the hash are retained.
            if payload_reference is None:
                payload_reference = f"secure://{job.id}/{task['evidence_requirement_id']}"
        else:
            stored_payload = json.dumps(result.payload)
    elif payload_reference is not None:
        payload_hash = hash_dict({"payload_reference": payload_reference})
    elif result.claims:
        # Claims-only evidence: the published claims are the bound content.
        payload_hash = hash_dict({"claims": result.claims})

    provenance = {
        "connector_id": connector.connector_id,
        "source_id": connector.connector_id,
        "source_type": connector.source_type,
        "auth_config_reference": connector.auth_config_reference,
        "is_mock": bool(connector.is_mock),
        "collected_via": "connector",
        "attempts": attempts,
        "orchestration_plan_id": job.orchestration_plan_id,
        "connector_trusted_issuers": list(connector.trusted_issuers),
        "signature_valid": result.signature_valid,
        "revoked": bool(result.revoked),
        "source_authority": bool(result.source_authority),
        "requirement": {
            "evidence_type": task.get("evidence_type"),
            "declared_source_type": task.get("declared_source_type"),
            "required_source_type": task.get("required_source_type"),
            "allowed_issuers": task.get("allowed_issuers", []),
            "freshness_threshold": task.get("freshness_threshold"),
            "expected_subject_id": task.get("subject_id"),
            "expected_target_id": task.get("target_id"),
            "expected_intent_id": task.get("intent_id")
            if task.get("bind_intent")
            else None,
            "mandatory": task.get("mandatory", True),
            "state": task.get("state"),
        },
    }

    raw = RawEvidence(
        organization_id=organization_id,
        collection_job_id=job.id,
        evidence_requirement_id=task["evidence_requirement_id"],
        policy_resolution_id=job.policy_resolution_id,
        source_id=connector.connector_id,
        source_type=connector.source_type,
        subject_id=result.subject_id
        if result.subject_id is not None
        else task.get("subject_id"),
        target_id=result.target_id
        if result.target_id is not None
        else task.get("target_id"),
        intent_id=result.intent_id
        if result.intent_id is not None
        else task.get("intent_id"),
        collected_at=collected_at,
        issued_at=result.issued_at,
        expires_at=result.expires_at,
        payload=stored_payload,
        payload_reference=payload_reference,
        payload_hash=payload_hash,
        claims=json.dumps(result.claims or {}),
        sensitivity=sensitivity,
        issuer=result.issuer,
        signature=result.signature,
        provenance=json.dumps(provenance),
        collection_status=result.status,
        error=result.error,
    )
    return RawEvidenceRepository(db).add(raw)


def run_collection(
    db: Session,
    organization_id: str,
    plan: EvidenceOrchestrationPlan,
    registry: ConnectorRegistry,
    *,
    production_mode: bool,
) -> EvidenceCollectionJob:
    """Execute a plan: collect in parallel, persist raw evidence + provenance."""
    tasks = _load(plan.tasks, []) or []
    plan_unresolved = _load(plan.unresolved, []) or []

    job = EvidenceCollectionJob(
        organization_id=organization_id,
        policy_resolution_id=plan.policy_resolution_id,
        evidence_requirement_set_id=plan.evidence_requirement_set_id,
        orchestration_plan_id=plan.id,
        production_mode=production_mode,
        status=EvidenceCollectionStatus.RUNNING.value,
        started_at=utc_now(),
    )
    job = EvidenceCollectionJobRepository(db).add(job)

    # --- collect in parallel where safe (connector calls are pure) --- #
    def _run_task(task: dict[str, Any]) -> tuple[dict[str, Any], EvidenceConnector, CollectResult, int]:
        connector = registry.get(task["connector_id"])
        if connector is None:
            return (
                task,
                _MissingConnector(task["connector_id"], task["source_type"]),
                CollectResult(
                    status=EvidenceCollectionStatus.FAILED.value,
                    payload=None,
                    error="connector no longer registered",
                ),
                0,
            )

        # Never use a mock connector silently in production mode.
        if production_mode and connector.is_mock:
            return (
                task,
                connector,
                CollectResult(
                    status=EvidenceCollectionStatus.REJECTED_MOCK.value,
                    payload=None,
                    error="mock connector rejected in production mode",
                    source_authority=False,
                ),
                0,
            )

        request = CollectRequest(
            evidence_requirement_id=task["evidence_requirement_id"],
            evidence_type=task["evidence_type"],
            source_type=task["source_type"],
            subject_id=task.get("subject_id"),
            target_id=task.get("target_id"),
            intent_id=task.get("intent_id"),
            allowed_issuers=task.get("allowed_issuers", []),
            freshness_threshold=task.get("freshness_threshold"),
        )
        result, attempts = _collect_with_retries(connector, request)
        return task, connector, result, attempts

    outcomes: list[tuple[dict[str, Any], EvidenceConnector, CollectResult, int]] = []
    if tasks:
        max_workers = min(8, len(tasks))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            outcomes = list(pool.map(_run_task, tasks))

    # --- persist sequentially (DB session is not thread-safe) --- #
    raw_ids: list[str] = []
    failures: list[dict[str, Any]] = []
    collected_count = 0
    for task, connector, result, attempts in outcomes:
        raw = _persist_raw_evidence(
            db,
            organization_id=organization_id,
            job=job,
            task=task,
            connector=connector,
            result=result,
            attempts=attempts,
        )
        raw_ids.append(raw.id)
        if result.status == EvidenceCollectionStatus.COLLECTED.value:
            collected_count += 1
        else:
            failures.append(
                {
                    "evidence_requirement_id": task["evidence_requirement_id"],
                    "connector_id": task.get("connector_id"),
                    "status": result.status,
                    "attempts": attempts,
                    "error": result.error,
                }
            )

    total_tasks = len(tasks)
    if total_tasks == 0 and not plan_unresolved:
        status = EvidenceCollectionStatus.COMPLETED.value
    elif collected_count == total_tasks and not plan_unresolved:
        status = EvidenceCollectionStatus.COMPLETED.value
    elif collected_count > 0:
        status = EvidenceCollectionStatus.PARTIAL.value
    else:
        status = EvidenceCollectionStatus.FAILED.value

    reason_codes = ["EVIDENCE_COLLECTION_" + status]
    if failures:
        reason_codes.append("EVIDENCE_COLLECTION_HAS_FAILURES")
    if plan_unresolved:
        reason_codes.append("EVIDENCE_COLLECTION_HAS_UNRESOLVED")

    job.status = status
    job.raw_evidence_ids = json.dumps(raw_ids)
    job.failures = json.dumps(failures)
    job.unresolved = json.dumps(plan_unresolved)
    job.reason_codes = json.dumps(reason_codes)
    job.completed_at = utc_now()
    return EvidenceCollectionJobRepository(db).save(job)


class _MissingConnector(EvidenceConnector):
    """Placeholder used only to carry provenance for a vanished connector."""

    supported_evidence_types: tuple[str, ...] = ()
    trusted_issuers: tuple[str, ...] = ()

    def __init__(self, connector_id: str, source_type: str) -> None:
        self.connector_id = connector_id
        self.source_type = source_type
        self.is_mock = False
        self.auth_config_reference = None

    def collect(self, request):  # pragma: no cover - never invoked
        raise ConnectorError("missing connector")

    def health_check(self):  # pragma: no cover
        raise ConnectorError("missing connector")

    def validate_connection(self):  # pragma: no cover
        return False


def resolve_production_mode(
    db: Session,
    organization_id: str,
    policy_resolution_id: str,
    requested: Optional[bool],
) -> bool:
    """Determine effective production mode.

    An explicit request wins. Otherwise the operational context environment is
    consulted: ``PRODUCTION`` implies production mode. Defaults to ``False``.
    """
    if requested is not None:
        return bool(requested)
    resolution = PolicyResolutionRepository(db).get(
        organization_id, policy_resolution_id
    )
    if resolution is None or not resolution.operational_context_id:
        return False
    context = OperationalContextRepository(db).get(
        organization_id, resolution.operational_context_id
    )
    if context is None:
        return False
    return context.environment == EnvironmentType.PRODUCTION.value
