from __future__ import annotations
from .base import CrudClient


class IntentClient(CrudClient):
    path = "intents"

    def transition(self, id: str, status: str, *, idempotency_key: str | None = None):
        return self._post(f"{self.path}/{id}/transition", {"status": status}, idempotency_key=idempotency_key)
