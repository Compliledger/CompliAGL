from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import replace
from typing import Any, Mapping

from .models import ExternalExecutionResult


def canonical_json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def result_payload_hash(result_payload: Mapping[str, Any] | None) -> str:
    return sha256_hex(canonical_json(result_payload or {}))


def canonical_signing_string(result: ExternalExecutionResult | Mapping[str, Any]) -> str:
    data = result.to_dict() if isinstance(result, ExternalExecutionResult) else dict(result)
    auth_id = data.get("authorization_id") or data.get("execution_authorization_id") or ""
    target = data.get("target")
    target_part = canonical_json(target) if isinstance(target, (dict, list)) else str(target or "")
    fields = [
        data.get("execution_result_id", ""),
        auth_id,
        data.get("external_system_id", ""),
        str(data.get("status", "")),
        data.get("executed_action", ""),
        target_part,
        "" if data.get("amount_minor") is None else str(data.get("amount_minor")),
        data.get("amount_currency") or "",
        data.get("external_reference") or "",
        data.get("payment_or_settlement_reference") or "",
        data.get("result_payload_hash", ""),
        data.get("executed_at", ""),
        data.get("submitted_at", ""),
    ]
    return "\n".join(fields)


class ResultSigner:
    def __init__(self, signing_secret: str, signer_key_id: str):
        self.signing_secret = signing_secret
        self.signer_key_id = signer_key_id

    def sign(self, result: ExternalExecutionResult) -> ExternalExecutionResult:
        return sign_execution_result(result, self.signing_secret, self.signer_key_id)


def sign_execution_result(result: ExternalExecutionResult, signing_secret: str, signer_key_id: str) -> ExternalExecutionResult:
    payload_hash = result_payload_hash(result.result_payload)
    prepared = replace(result, result_payload_hash=payload_hash, signer_key_id=signer_key_id, signature="")
    signature = hmac.new(signing_secret.encode("utf-8"), canonical_signing_string(prepared).encode("utf-8"), hashlib.sha256).hexdigest()
    return replace(prepared, signature=signature)


signExecutionResult = sign_execution_result


def verify_execution_result_signature(result: ExternalExecutionResult | Mapping[str, Any], signing_secret: str) -> bool:
    data = result.to_dict() if isinstance(result, ExternalExecutionResult) else dict(result)
    expected_hash = result_payload_hash(data.get("result_payload"))
    if not hmac.compare_digest(str(data.get("result_payload_hash", "")), expected_hash):
        return False
    actual = str(data.get("signature", ""))
    data["signature"] = ""
    expected = hmac.new(signing_secret.encode("utf-8"), canonical_signing_string(data).encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(actual, expected)


verifyExecutionResultSignature = verify_execution_result_signature
