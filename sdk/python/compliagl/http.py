from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from .config import CompliAGLConfig
from .errors import AuthError, CompliAGLApiError, ConflictError, NotFoundError, RateLimitError, ServerError, ValidationError

_RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


class HttpClient:
    def __init__(self, config: CompliAGLConfig):
        self.config = config

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        method = method.upper()
        if method == "POST" and not idempotency_key and self.config.auto_idempotency:
            idempotency_key = str(uuid.uuid4())
        url = self._url(path, params)
        body = None if json_body is None else json.dumps(json_body, separators=(",", ":")).encode("utf-8")
        headers = self._headers(method, idempotency_key, body is not None)
        attempts = self.config.max_retries + 1
        retryable = method == "GET" or (method == "POST" and bool(idempotency_key))
        last_error: Exception | None = None
        for attempt in range(attempts):
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                    data = resp.read()
                    if not data:
                        return None
                    return json.loads(data.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                parsed = self._parse_error_body(exc)
                if retryable and exc.code in _RETRY_STATUSES and attempt < attempts - 1:
                    self._sleep(attempt, exc.headers.get("Retry-After"))
                    continue
                raise self._error_for_status(exc.code, parsed) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if retryable and attempt < attempts - 1:
                    self._sleep(attempt, None)
                    continue
                raise CompliAGLApiError(None, "network_error", str(exc), None) from exc
        raise CompliAGLApiError(None, "network_error", str(last_error), None)

    def _url(self, path: str, params: dict[str, Any] | None) -> str:
        base = f"{self.config.base_url}/api/v1/{path.lstrip('/')}"
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        if clean:
            return base + "?" + urllib.parse.urlencode(clean)
        return base

    def _headers(self, method: str, idempotency_key: str | None, has_body: bool) -> dict[str, str]:
        headers = {"Accept": "application/json", "X-Organization-Id": self.config.organization_id}
        if self.config.api_key:
            headers["Authorization"] = "Bearer " + self.config.api_key
        if has_body or method in {"POST", "PATCH"}:
            headers["Content-Type"] = "application/json"
        if method == "POST" and idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _sleep(self, attempt: int, retry_after: str | None) -> None:
        delay = None
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = None
        if delay is None:
            base = self.config.retry_base_ms / 1000.0
            delay = base * (2 ** attempt) + random.uniform(0, base)
        time.sleep(delay)

    def _parse_error_body(self, exc: urllib.error.HTTPError) -> dict[str, Any]:
        try:
            raw = exc.read().decode("utf-8")
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def _error_for_status(self, status: int, body: dict[str, Any]) -> CompliAGLApiError:
        code = body.get("code") or body.get("error") or str(status)
        message = body.get("message") or body.get("detail") or f"HTTP {status}"
        if status == 404:
            return NotFoundError(status, code, message, body)
        if status in {400, 422}:
            return ValidationError(status, code, message, body)
        if status == 409:
            return ConflictError(status, code, message, body)
        if status == 429:
            return RateLimitError(status, code, message, body)
        if status in {401, 403}:
            return AuthError(status, code, message, body)
        if status >= 500:
            return ServerError(status, code, message, body)
        return CompliAGLApiError(status, code, message, body)
