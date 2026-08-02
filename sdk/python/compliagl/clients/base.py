from __future__ import annotations

from typing import Any

from ..http import HttpClient


class BaseClient:
    def __init__(self, http: HttpClient):
        self.http = http

    def _post(self, path: str, data: dict[str, Any] | None = None, *, idempotency_key: str | None = None):
        return self.http.request("POST", path, json_body=data or {}, idempotency_key=idempotency_key)

    def _get(self, path: str, params: dict[str, Any] | None = None):
        return self.http.request("GET", path, params=params)

    def _patch(self, path: str, data: dict[str, Any] | None = None):
        return self.http.request("PATCH", path, json_body=data or {})


class CrudClient(BaseClient):
    path: str

    def create(self, data: dict[str, Any], *, idempotency_key: str | None = None):
        return self._post(self.path, data, idempotency_key=idempotency_key)

    def list(self, *, skip: int | None = None, limit: int | None = None):
        return self._get(self.path, {"skip": skip, "limit": limit})

    def get(self, id: str):
        return self._get(f"{self.path}/{id}")

    def update(self, id: str, data: dict[str, Any]):
        return self._patch(f"{self.path}/{id}", data)
