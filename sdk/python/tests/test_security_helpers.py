import hashlib
import hmac
import time
import uuid

import pytest

from compliagl import ExecutionResultStatus, ExternalExecutionResult, WebhookVerificationError
from compliagl.signing import ResultSigner, canonical_json, sign_execution_result, verify_execution_result_signature
from compliagl.webhooks import verify_webhook_signature


def unsigned_result():
    now = "2026-08-02T13:00:00Z"
    return ExternalExecutionResult(
        execution_result_id=str(uuid.uuid4()),
        authorization_id="auth_1",
        external_system_id="outside_system",
        status=ExecutionResultStatus.SUCCEEDED,
        executed_action="capture_order",
        target={"merchant": "m1"},
        amount_minor=500,
        amount_currency="USD",
        external_reference="ext_1",
        payment_or_settlement_reference="pay_1",
        result_payload_hash="",
        executed_at=now,
        submitted_at=now,
        signer_key_id="",
        signature="",
        provenance={"adapter": "test"},
        result_payload={"ok": True, "amount_minor": 500},
    )


def test_result_signing_and_verification():
    signed = ResultSigner("test-secret", "test-key").sign(unsigned_result())
    assert signed.result_payload_hash == hashlib.sha256(canonical_json(signed.result_payload).encode()).hexdigest()
    assert verify_execution_result_signature(signed, "test-secret") is True
    tampered = signed.to_dict()
    tampered["result_payload"] = {"ok": False}
    assert verify_execution_result_signature(tampered, "test-secret") is False


def test_webhook_signature_valid_tampered_expired():
    secret = "whsec"
    payload = b'{"event":"proof.created"}'
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + payload, hashlib.sha256).hexdigest()
    headers = {"X-CompliAGL-Timestamp": ts, "X-CompliAGL-Signature": f"sha256={sig}"}
    assert verify_webhook_signature(payload, headers, secret)
    with pytest.raises(WebhookVerificationError):
        verify_webhook_signature(b'{"event":"other"}', headers, secret)
    old = str(int(time.time()) - 1000)
    old_sig = hmac.new(secret.encode(), old.encode() + b"." + payload, hashlib.sha256).hexdigest()
    with pytest.raises(WebhookVerificationError):
        verify_webhook_signature(payload, {"X-CompliAGL-Timestamp": old, "X-CompliAGL-Signature": f"sha256={old_sig}"}, secret, tolerance_seconds=1)
