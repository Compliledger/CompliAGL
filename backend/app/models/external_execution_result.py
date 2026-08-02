"""ExternalExecutionResult ORM model — canonical first-class resource.

An **ExternalExecutionResult** captures the outcome of an authorized action
executed through an external adapter (payment rail, API, chain, ...). It records
the adapter used, the settlement reference, and the resulting status/payload so
the AIProof can bind the real outcome.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import ExecutionResultStatus


class ExternalExecutionResult(CanonicalMixin, Base):
    """Persistent result of an externally executed, authorized action."""

    __tablename__ = "external_execution_results"

    execution_authorization_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)

    adapter = Column(String, nullable=True)
    status = Column(
        String, nullable=False, default=ExecutionResultStatus.PENDING.value
    )
    external_reference = Column(String, nullable=True, index=True)
    settlement_chain = Column(String, nullable=True)

    result_payload = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    executed_at = Column(DateTime(timezone=True), nullable=True)
