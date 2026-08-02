from __future__ import annotations
from typing import Any
from .base import BaseClient


class DecisionClient(BaseClient):
    path = "decisions"

    def create(self, data: dict[str, Any], *, idempotency_key: str | None = None):
        return self._post(self.path, data, idempotency_key=idempotency_key)

    def list(self, *, skip: int | None = None, limit: int | None = None):
        return self._get(self.path, {"skip": skip, "limit": limit})

    def get(self, id: str):
        return self._get(f"{self.path}/{id}")

    def decide(self, organization_id: str, policy_resolution_id: str, prior_decision_id: str | None = None, *, idempotency_key: str | None = None):
        return self._post(f"{self.path}/decide", {"organization_id": organization_id, "policy_resolution_id": policy_resolution_id, "prior_decision_id": prior_decision_id}, idempotency_key=idempotency_key)

    def explain(self, id: str):
        return self._get(f"{self.path}/{id}/explain")
