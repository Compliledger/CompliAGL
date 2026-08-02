from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CompliAGLConfig:
    organization_id: str
    base_url: str = "http://localhost:8000"
    api_key: str | None = None
    timeout: float = 30.0
    max_retries: int = 3
    retry_base_ms: int = 200
    auto_idempotency: bool = False
    webhook_secret: str | None = None

    def __init__(
        self,
        organization_id: str | None = None,
        *,
        organizationId: str | None = None,
        base_url: str | None = None,
        baseUrl: str | None = None,
        api_key: str | None = None,
        apiKey: str | None = None,
        timeout: float = 30.0,
        max_retries: int | None = None,
        maxRetries: int | None = None,
        retry_base_ms: int | None = None,
        retryBaseMs: int | None = None,
        auto_idempotency: bool | None = None,
        autoIdempotency: bool | None = None,
        webhook_secret: str | None = None,
        webhookSecret: str | None = None,
    ):
        org = organization_id or organizationId
        if not org:
            raise ValueError("organization_id is required")
        self.organization_id = org
        self.base_url = (base_url or baseUrl or "http://localhost:8000").rstrip("/")
        self.api_key = api_key if api_key is not None else apiKey
        self.timeout = timeout
        self.max_retries = 3 if max_retries is None and maxRetries is None else (max_retries if max_retries is not None else maxRetries)  # type: ignore[assignment]
        self.retry_base_ms = 200 if retry_base_ms is None and retryBaseMs is None else (retry_base_ms if retry_base_ms is not None else retryBaseMs)  # type: ignore[assignment]
        self.auto_idempotency = bool(auto_idempotency if auto_idempotency is not None else (autoIdempotency if autoIdempotency is not None else False))
        self.webhook_secret = webhook_secret if webhook_secret is not None else webhookSecret
