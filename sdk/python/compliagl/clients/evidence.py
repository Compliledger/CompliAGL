from __future__ import annotations
from typing import Any
from .base import BaseClient


class EvidenceClient(BaseClient):
    def create(self, data: dict[str, Any], *, idempotency_key: str | None = None):
        return self._post("evidence-collections", data, idempotency_key=idempotency_key)

    def get(self, job_id: str):
        return self._get(f"evidence-collections/{job_id}")

    def package(self, job_id: str):
        return self._get(f"evidence-collections/{job_id}/package")

    def sources(self):
        return self._get("evidence-sources")
