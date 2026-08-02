"""Tenant-scoped repositories for canonical first-class resources.

The :class:`TenantRepository` base guarantees that every read/list/count query
is filtered by ``organization_id``. Callers must always pass the tenant, so a
missing or mismatched tenant can never leak another organization's data.
"""

from __future__ import annotations

from typing import Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy.orm import Session

from app.models.actor_identity import ActorIdentity
from app.models.decision import Decision
from app.models.execution_authorization import ExecutionAuthorization
from app.models.external_execution_result import ExternalExecutionResult
from app.models.governance_evaluation import GovernanceEvaluation
from app.models.intent import Intent
from app.models.operational_context import OperationalContext
from app.models.target import Target

ModelT = TypeVar("ModelT")


class TenantRepository(Generic[ModelT]):
    """Base repository enforcing tenant isolation on every query."""

    model: Type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- internal ---------------------------------------------------------- #
    def _scoped(self, organization_id: str):
        """Return a base query already filtered to the tenant."""
        if not organization_id:
            raise ValueError("organization_id is required for tenant isolation")
        return self.db.query(self.model).filter(
            self.model.organization_id == organization_id  # type: ignore[attr-defined]
        )

    # -- reads ------------------------------------------------------------- #
    def get(self, organization_id: str, resource_id: str) -> Optional[ModelT]:
        return (
            self._scoped(organization_id)
            .filter(self.model.id == resource_id)  # type: ignore[attr-defined]
            .first()
        )

    def list(
        self, organization_id: str, *, skip: int = 0, limit: int = 100
    ) -> Sequence[ModelT]:
        return (
            self._scoped(organization_id)
            .order_by(self.model.created_at.asc())  # type: ignore[attr-defined]
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, organization_id: str) -> int:
        return self._scoped(organization_id).count()

    def find_one(self, organization_id: str, **filters) -> Optional[ModelT]:
        """Return the first row in the tenant matching equality ``filters``."""
        query = self._scoped(organization_id)
        for attribute, value in filters.items():
            query = query.filter(getattr(self.model, attribute) == value)
        return query.first()

    # -- writes ------------------------------------------------------------ #
    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def save(self, obj: ModelT) -> ModelT:
        """Persist in-place mutations to an already-tracked instance."""
        self.db.commit()
        self.db.refresh(obj)
        return obj


class ActorIdentityRepository(TenantRepository[ActorIdentity]):
    model = ActorIdentity


class IntentRepository(TenantRepository[Intent]):
    model = Intent


class TargetRepository(TenantRepository[Target]):
    model = Target


class OperationalContextRepository(TenantRepository[OperationalContext]):
    model = OperationalContext


class GovernanceEvaluationRepository(TenantRepository[GovernanceEvaluation]):
    model = GovernanceEvaluation


class DecisionRepository(TenantRepository[Decision]):
    model = Decision


class ExecutionAuthorizationRepository(TenantRepository[ExecutionAuthorization]):
    model = ExecutionAuthorization


class ExternalExecutionResultRepository(TenantRepository[ExternalExecutionResult]):
    model = ExternalExecutionResult
