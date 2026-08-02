from __future__ import annotations
from typing import Any
from .base import BaseClient


class AuthorizationClient(BaseClient):
    path = "execution-authorizations"

    def create(self, data: dict[str, Any], *, idempotency_key: str | None = None):
        return self._post(self.path, data, idempotency_key=idempotency_key)

    def issue(self, data: dict[str, Any], *, idempotency_key: str | None = None):
        return self._post(f"{self.path}/issue", data, idempotency_key=idempotency_key)

    def list(self, *, skip: int | None = None, limit: int | None = None):
        return self._get(self.path, {"skip": skip, "limit": limit})

    def get(self, id: str):
        return self._get(f"{self.path}/{id}")

    def verify(self, id: str, expected_fields: dict[str, Any] | None = None, activate: bool = False, *, idempotency_key: str | None = None):
        return self._post(f"{self.path}/{id}/verify", {"expected_fields": expected_fields or {}, "activate": activate}, idempotency_key=idempotency_key)

    def consume(self, id: str, *, idempotency_key: str | None = None):
        return self._post(f"{self.path}/{id}/consume", {}, idempotency_key=idempotency_key)

    def revoke(self, id: str, reason: str | None = None, *, idempotency_key: str | None = None):
        return self._post(f"{self.path}/{id}/revoke", {"reason": reason}, idempotency_key=idempotency_key)

    def transition(self, id: str, status: str, *, idempotency_key: str | None = None):
        return self._post(f"{self.path}/{id}/transition", {"status": status}, idempotency_key=idempotency_key)
