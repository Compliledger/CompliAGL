from __future__ import annotations
from typing import Any
from .base import BaseClient
from ..signing import verify_execution_result_signature


class VerificationClient(BaseClient):
    def verify_authorization(self, id: str, expected_fields: dict[str, Any] | None = None):
        return self._post(f"execution-authorizations/{id}/verify", {"expected_fields": expected_fields or {}, "activate": False})

    verifyAuthorization = verify_authorization

    def verify_proof(self, proof_id: str):
        return self._get(f"aiproofs/{proof_id}/verify")

    verifyProof = verify_proof

    def verify_execution_result_binding(self, result: dict[str, Any], secret: str) -> bool:
        return verify_execution_result_signature(result, secret)

    verifyExecutionResultBinding = verify_execution_result_binding
