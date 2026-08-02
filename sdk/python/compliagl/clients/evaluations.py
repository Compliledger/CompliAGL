from __future__ import annotations
from typing import Any
from .base import BaseClient


class EvaluationClient(BaseClient):
    path = "governance-evaluations"

    def create(self, data: dict[str, Any], *, idempotency_key: str | None = None):
        return self._post(self.path, data, idempotency_key=idempotency_key)

    def list(self, *, skip: int | None = None, limit: int | None = None):
        return self._get(self.path, {"skip": skip, "limit": limit})

    def get(self, id: str):
        return self._get(f"{self.path}/{id}")

    def resolve(self, id: str, outcome: str, reason_codes: list[str] | None = None, status: str | None = None, *, idempotency_key: str | None = None):
        return self._post(f"{self.path}/{id}/resolve", {"outcome": outcome, "reason_codes": reason_codes or [], "status": status}, idempotency_key=idempotency_key)
