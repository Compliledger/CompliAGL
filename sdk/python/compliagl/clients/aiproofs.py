from __future__ import annotations
from .base import BaseClient


class AIProofClient(BaseClient):
    def generate(self, execution_result_id: str, *, idempotency_key: str | None = None):
        return self._post("aiproofs/generate", {"execution_result_id": execution_result_id}, idempotency_key=idempotency_key)

    def get(self, id: str):
        return self._get(f"aiproofs/{id}")

    def list(self, *, skip: int | None = None, limit: int | None = None):
        return self._get("aiproofs", {"skip": skip, "limit": limit})

    def verify(self, id: str):
        return self._get(f"aiproofs/{id}/verify")
