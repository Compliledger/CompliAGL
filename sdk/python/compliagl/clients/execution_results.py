from __future__ import annotations
from typing import Any
from .base import BaseClient
from ..models import ExternalExecutionResult


class ExecutionResultClient(BaseClient):
    path = "external-execution-results"

    def create(self, data: dict[str, Any] | ExternalExecutionResult, *, idempotency_key: str | None = None):
        body = data.to_dict() if isinstance(data, ExternalExecutionResult) else data
        return self._post(self.path, body, idempotency_key=idempotency_key)

    def list(self, *, skip: int | None = None, limit: int | None = None):
        return self._get(self.path, {"skip": skip, "limit": limit})

    def get(self, id: str):
        return self._get(f"{self.path}/{id}")
