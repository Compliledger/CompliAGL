from __future__ import annotations

import hashlib
import hmac
import time

from .errors import WebhookVerificationError


def verify_webhook_signature(payload: str | bytes, headers: dict[str, str], secret: str, tolerance_seconds: int = 300) -> bool:
    normalized = {k.lower(): v for k, v in headers.items()}
    signature_header = normalized.get("x-compliagl-signature")
    timestamp = normalized.get("x-compliagl-timestamp")
    if not signature_header or not timestamp:
        raise WebhookVerificationError("missing webhook signature headers")
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise WebhookVerificationError("invalid webhook timestamp") from exc
    if abs(time.time() - ts) > tolerance_seconds:
        raise WebhookVerificationError("webhook timestamp outside tolerance")
    if not signature_header.startswith("sha256="):
        raise WebhookVerificationError("unsupported webhook signature algorithm")
    body = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    signed = timestamp.encode("utf-8") + b"." + body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature_header[len("sha256="):], expected):
        raise WebhookVerificationError("webhook signature mismatch")
    return True


verifyWebhookSignature = verify_webhook_signature
