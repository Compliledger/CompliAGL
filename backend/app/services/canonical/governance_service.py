"""Governance chain services.

Covers the four resources that bind the runtime together after an intent is
submitted:

* :class:`GovernanceEvaluation` — ties actor, intent, target, and context,
* :class:`Decision` — the deterministic verdict,
* :class:`ExecutionAuthorization` — the gate before external execution,
* :class:`ExternalExecutionResult` — the recorded outcome.
"""

from __future__ import annotations

import json
import uuid
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.execution_authorization import ExecutionAuthorization
from app.models.external_execution_result import ExternalExecutionResult
from app.models.governance_evaluation import GovernanceEvaluation
from app.repositories.canonical import (
    ActorIdentityRepository,
    DecisionRepository,
    ExecutionAuthorizationRepository,
    ExternalExecutionResultRepository,
    GovernanceEvaluationRepository,
    IntentRepository,
)
from app.schemas.canonical.governance import (
    DecisionCreate,
    ExecutionAuthorizationCreate,
    ExternalExecutionResultCreate,
    GovernanceEvaluationCreate,
    GovernanceEvaluationResolve,
)
from app.services.canonical.errors import NotFoundError
from app.services.canonical.transitions import (
    AUTHORIZATION_TRANSITIONS,
    validate_transition,
)
from app.utils.canonical_enums import (
    AuthorizationStatus,
    EvaluationStatus,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


# --------------------------------------------------------------------------- #
# GovernanceEvaluation
# --------------------------------------------------------------------------- #
def create_evaluation(
    db: Session, payload: GovernanceEvaluationCreate
) -> GovernanceEvaluation:
    """Create the record tying actor, intent, target, and context together.

    The referenced actor identity and intent must already exist in the tenant.
    """
    org = payload.organization_id
    if ActorIdentityRepository(db).get(org, payload.actor_identity_id) is None:
        raise NotFoundError(f"ActorIdentity not found: {payload.actor_identity_id}")
    if IntentRepository(db).get(org, payload.intent_id) is None:
        raise NotFoundError(f"Intent not found: {payload.intent_id}")

    evaluation_hash = hash_dict(
        {
            "organization_id": org,
            "actor_identity_id": payload.actor_identity_id,
            "intent_id": payload.intent_id,
            "target_id": payload.target_id,
            "operational_context_id": payload.operational_context_id,
        }
    )
    obj = GovernanceEvaluation(
        organization_id=org,
        actor_identity_id=payload.actor_identity_id,
        intent_id=payload.intent_id,
        target_id=payload.target_id,
        operational_context_id=payload.operational_context_id,
        status=EvaluationStatus.PENDING.value,
        reason_codes="[]",
        evaluation_hash=evaluation_hash,
    )
    return GovernanceEvaluationRepository(db).add(obj)


def get_evaluation(
    db: Session, organization_id: str, resource_id: str
) -> Optional[GovernanceEvaluation]:
    return GovernanceEvaluationRepository(db).get(organization_id, resource_id)


def list_evaluations(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[GovernanceEvaluation]:
    return GovernanceEvaluationRepository(db).list(
        organization_id, skip=skip, limit=limit
    )


def resolve_evaluation(
    db: Session,
    organization_id: str,
    resource_id: str,
    payload: GovernanceEvaluationResolve,
) -> Optional[GovernanceEvaluation]:
    repo = GovernanceEvaluationRepository(db)
    obj = repo.get(organization_id, resource_id)
    if obj is None:
        return None
    obj.status = payload.status.value
    obj.outcome = payload.outcome.value
    obj.reason_codes = json.dumps(payload.reason_codes)
    return repo.save(obj)


# --------------------------------------------------------------------------- #
# Decision
# --------------------------------------------------------------------------- #
def create_decision(db: Session, payload: DecisionCreate) -> Decision:
    org = payload.organization_id
    evaluation = GovernanceEvaluationRepository(db).get(
        org, payload.governance_evaluation_id
    )
    if evaluation is None:
        raise NotFoundError(
            f"GovernanceEvaluation not found: {payload.governance_evaluation_id}"
        )
    decision_hash = hash_dict(
        {
            "organization_id": org,
            "governance_evaluation_id": payload.governance_evaluation_id,
            "intent_id": payload.intent_id,
            "outcome": payload.outcome.value,
            "reason_codes": payload.reason_codes,
            "policy_version": payload.policy_version,
        }
    )
    obj = Decision(
        organization_id=org,
        governance_evaluation_id=payload.governance_evaluation_id,
        intent_id=payload.intent_id,
        outcome=payload.outcome.value,
        reason_codes=json.dumps(payload.reason_codes),
        policy_version=payload.policy_version,
        decision_hash=decision_hash,
        decided_at=utc_now(),
    )
    return DecisionRepository(db).add(obj)


def get_decision(
    db: Session, organization_id: str, resource_id: str
) -> Optional[Decision]:
    return DecisionRepository(db).get(organization_id, resource_id)


def list_decisions(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[Decision]:
    return DecisionRepository(db).list(organization_id, skip=skip, limit=limit)


# --------------------------------------------------------------------------- #
# ExecutionAuthorization
# --------------------------------------------------------------------------- #
def create_authorization(
    db: Session, payload: ExecutionAuthorizationCreate
) -> ExecutionAuthorization:
    org = payload.organization_id
    if DecisionRepository(db).get(org, payload.decision_id) is None:
        raise NotFoundError(f"Decision not found: {payload.decision_id}")
    obj = ExecutionAuthorization(
        organization_id=org,
        decision_id=payload.decision_id,
        intent_id=payload.intent_id,
        status=AuthorizationStatus.AUTHORIZED.value,
        authorization_token=uuid.uuid4().hex,
        constraints=(
            json.dumps(payload.constraints)
            if payload.constraints is not None
            else None
        ),
        authorized_at=utc_now(),
        expires_at=payload.expires_at,
    )
    return ExecutionAuthorizationRepository(db).add(obj)


def get_authorization(
    db: Session, organization_id: str, resource_id: str
) -> Optional[ExecutionAuthorization]:
    return ExecutionAuthorizationRepository(db).get(organization_id, resource_id)


def list_authorizations(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[ExecutionAuthorization]:
    return ExecutionAuthorizationRepository(db).list(
        organization_id, skip=skip, limit=limit
    )


def transition_authorization(
    db: Session,
    organization_id: str,
    resource_id: str,
    new_status: AuthorizationStatus,
) -> Optional[ExecutionAuthorization]:
    repo = ExecutionAuthorizationRepository(db)
    obj = repo.get(organization_id, resource_id)
    if obj is None:
        return None
    validate_transition(
        "ExecutionAuthorization",
        AUTHORIZATION_TRANSITIONS,
        obj.status,
        new_status.value,
    )
    obj.status = new_status.value
    return repo.save(obj)


# --------------------------------------------------------------------------- #
# ExternalExecutionResult
# --------------------------------------------------------------------------- #
def create_execution_result(
    db: Session, payload: ExternalExecutionResultCreate
) -> ExternalExecutionResult:
    org = payload.organization_id
    if (
        ExecutionAuthorizationRepository(db).get(
            org, payload.execution_authorization_id
        )
        is None
    ):
        raise NotFoundError(
            f"ExecutionAuthorization not found: {payload.execution_authorization_id}"
        )
    obj = ExternalExecutionResult(
        organization_id=org,
        execution_authorization_id=payload.execution_authorization_id,
        intent_id=payload.intent_id,
        adapter=payload.adapter,
        status=payload.status.value,
        external_reference=payload.external_reference,
        settlement_chain=payload.settlement_chain,
        result_payload=(
            json.dumps(payload.result_payload)
            if payload.result_payload is not None
            else None
        ),
        error=payload.error,
        executed_at=utc_now(),
    )
    return ExternalExecutionResultRepository(db).add(obj)


def get_execution_result(
    db: Session, organization_id: str, resource_id: str
) -> Optional[ExternalExecutionResult]:
    return ExternalExecutionResultRepository(db).get(organization_id, resource_id)


def list_execution_results(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[ExternalExecutionResult]:
    return ExternalExecutionResultRepository(db).list(
        organization_id, skip=skip, limit=limit
    )
