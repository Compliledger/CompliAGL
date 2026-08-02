from __future__ import annotations

import hashlib
import hmac
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from compliagl.signing import canonical_json, verify_execution_result_signature


class MockState:
    def __init__(self):
        self.lock = threading.RLock()
        self.collections: dict[str, dict[str, dict[str, Any]]] = {
            "actor-identities": {},
            "intents": {},
            "targets": {},
            "operational-contexts": {},
            "governance-evaluations": {},
            "evidence-collections": {},
            "decisions": {},
            "execution-authorizations": {},
            "external-execution-results": {},
            "aiproofs": {},
        }
        self.idempotency: dict[tuple[str, str, str], tuple[int, Any]] = {}
        self.failures: dict[tuple[str, str], int] = {}
        self.last_headers: dict[str, str] = {}
        self.signer_secrets = {"test-key": "test-secret", "demo-key": "demo-secret"}
        self.proof_secret = "mock-proof-secret"

    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"


class MockHandler(BaseHTTPRequestHandler):
    server_version = "CompliAGLMock/1.0"
    state: MockState

    def log_message(self, format, *args):
        return

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PATCH(self):
        self._handle("PATCH")

    def _handle(self, method: str):
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/v1/"):
            return self._send(404, {"code": "not_found", "message": "unknown prefix"})
        rel = path[len("/api/v1/"):].strip("/")
        key = (method, rel)
        with self.state.lock:
            self.state.last_headers = {k: v for k, v in self.headers.items()}
            if self.state.failures.get(key, 0) > 0:
                self.state.failures[key] -= 1
                return self._send(503, {"code": "temporary", "message": "temporary failure"}, {"Retry-After": "0"})
        idem = self.headers.get("Idempotency-Key")
        idem_key = (method, rel, idem or "")
        if method == "POST" and idem:
            with self.state.lock:
                if idem_key in self.state.idempotency:
                    status, body = self.state.idempotency[idem_key]
                    return self._send(status, body)
        body = self._read_json()
        try:
            status, response = self._route(method, rel, parse_qs(parsed.query), body)
        except ValueError as exc:
            status, response = 422, {"code": "validation_error", "message": str(exc)}
        except KeyError as exc:
            status, response = 404, {"code": "not_found", "message": str(exc)}
        if method == "POST" and idem and 200 <= status < 300:
            with self.state.lock:
                self.state.idempotency[idem_key] = (status, response)
        self._send(status, response)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _send(self, status: int, body: Any, headers: dict[str, str] | None = None):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _route(self, method: str, rel: str, query: dict[str, list[str]], body: dict[str, Any]) -> tuple[int, Any]:
        parts = rel.split("/") if rel else []
        if rel == "evidence-sources" and method == "GET":
            return 200, {"items": [{"id": "source_mock", "type": "mock"}]}
        if parts[:1] == ["evidence-collections"]:
            return self._evidence(method, parts, body)
        if parts[:1] == ["decisions"]:
            return self._decisions(method, parts, query, body)
        if parts[:1] == ["execution-authorizations"]:
            return self._authorizations(method, parts, query, body)
        if parts[:1] == ["external-execution-results"]:
            return self._execution_results(method, parts, query, body)
        if parts[:1] == ["aiproofs"]:
            return self._aiproofs(method, parts, query, body)
        generic = {"actor-identities", "intents", "targets", "operational-contexts", "governance-evaluations"}
        if parts and parts[0] in generic:
            if parts[0] == "intents" and len(parts) == 3 and parts[2] == "transition" and method == "POST":
                item = self._get_item("intents", parts[1])
                item["status"] = body.get("status")
                return 200, item
            if parts[0] == "governance-evaluations" and len(parts) == 3 and parts[2] == "resolve" and method == "POST":
                item = self._get_item("governance-evaluations", parts[1])
                item.update({"outcome": body.get("outcome"), "reason_codes": body.get("reason_codes", []), "status": body.get("status") or "RESOLVED"})
                return 200, item
            return self._crud(parts[0], method, parts, query, body)
        raise KeyError(rel)

    def _crud(self, collection: str, method: str, parts: list[str], query, body) -> tuple[int, Any]:
        if len(parts) == 1 and method == "POST":
            item = dict(body)
            item.setdefault("id", self.state.new_id(collection[:-1].replace("-", "_")))
            self.state.collections[collection][item["id"]] = item
            return 201, item
        if len(parts) == 1 and method == "GET":
            return 200, self._list(collection, query)
        if len(parts) == 2 and method == "GET":
            return 200, self._get_item(collection, parts[1])
        if len(parts) == 2 and method == "PATCH":
            item = self._get_item(collection, parts[1])
            item.update(body)
            return 200, item
        raise KeyError("unsupported")

    def _list(self, collection: str, query) -> dict[str, Any]:
        items = list(self.state.collections[collection].values())
        skip = int(query.get("skip", [0])[0] or 0)
        limit = int(query.get("limit", [len(items)])[0] or len(items))
        return {"items": items[skip:skip + limit], "skip": skip, "limit": limit, "total": len(items)}

    def _get_item(self, collection: str, id: str) -> dict[str, Any]:
        try:
            return self.state.collections[collection][id]
        except KeyError:
            raise KeyError(f"{collection}/{id}")

    def _evidence(self, method, parts, body):
        if len(parts) == 1 and method == "POST":
            job_id = body.get("job_id") or self.state.new_id("evidence_job")
            item = {**body, "id": job_id, "job_id": job_id, "status": "COMPLETED", "items": body.get("items", [])}
            self.state.collections["evidence-collections"][job_id] = item
            return 201, item
        if len(parts) == 2 and method == "GET":
            return 200, self._get_item("evidence-collections", parts[1])
        if len(parts) == 3 and parts[2] == "package" and method == "GET":
            item = self._get_item("evidence-collections", parts[1])
            return 200, {"job_id": parts[1], "package_hash": hashlib.sha256(canonical_json(item).encode()).hexdigest(), "items": item.get("items", [])}
        raise KeyError("evidence")

    def _decisions(self, method, parts, query, body):
        if len(parts) == 2 and parts[1] == "decide" and method == "POST":
            item = {"id": self.state.new_id("dec"), "policy_resolution_id": body.get("policy_resolution_id"), "prior_decision_id": body.get("prior_decision_id"), "outcome": "APPROVED", "reason_codes": ["MOCK_APPROVED"]}
            self.state.collections["decisions"][item["id"]] = item
            return 201, item
        if len(parts) == 3 and parts[2] == "explain" and method == "GET":
            item = self._get_item("decisions", parts[1])
            return 200, {"decision_id": parts[1], "outcome": item.get("outcome"), "explanation": "mock server response"}
        return self._crud("decisions", method, parts, query, body)

    def _authorizations(self, method, parts, query, body):
        if len(parts) == 2 and parts[1] == "issue" and method == "POST":
            item = {**body, "id": body.get("id") or self.state.new_id("auth"), "status": "ISSUED", "signature": "mock-auth-signature"}
            self.state.collections["execution-authorizations"][item["id"]] = item
            return 201, item
        if len(parts) == 1:
            return self._crud("execution-authorizations", method, parts, query, body)
        if len(parts) == 2 and method in {"GET", "PATCH"}:
            return self._crud("execution-authorizations", method, parts, query, body)
        item = self._get_item("execution-authorizations", parts[1])
        if len(parts) == 3 and method == "POST":
            action = parts[2]
            if action == "verify":
                expected = body.get("expected_fields") or {}
                for k, v in expected.items():
                    if item.get(k) != v:
                        return 409, {"code": "authorization_mismatch", "message": f"{k} mismatch"}
                if body.get("activate"):
                    item["status"] = "ACTIVE"
                return 200, {"valid": item.get("status") in {"ISSUED", "ACTIVE", "AUTHORIZED"}, "authorization": item}
            if action == "consume":
                item["status"] = "CONSUMED"
                return 200, item
            if action == "revoke":
                item["status"] = "REVOKED"
                item["revocation_reason"] = body.get("reason")
                return 200, item
            if action == "transition":
                item["status"] = body.get("status")
                return 200, item
        raise KeyError("authorization")

    def _execution_results(self, method, parts, query, body):
        if len(parts) == 1 and method == "POST":
            auth_id = body.get("execution_authorization_id") or body.get("authorization_id")
            if not auth_id:
                raise ValueError("missing authorization binding")
            auth = self._get_item("execution-authorizations", auth_id)
            if auth.get("status") not in {"ISSUED", "ACTIVE", "AUTHORIZED"}:
                return 409, {"code": "authorization_not_usable", "message": "authorization is not usable"}
            expected_hash = hashlib.sha256(canonical_json(body.get("result_payload") or {}).encode("utf-8")).hexdigest()
            if body.get("result_payload_hash") != expected_hash:
                return 422, {"code": "payload_hash_mismatch", "message": "result payload hash mismatch"}
            secret = self.state.signer_secrets.get(body.get("signer_key_id"))
            if not secret or not verify_execution_result_signature(body, secret):
                return 409, {"code": "invalid_result_signature", "message": "result signature invalid"}
            if auth.get("max_amount_minor") is not None and body.get("amount_minor") is not None and int(body["amount_minor"]) > int(auth["max_amount_minor"]):
                return 409, {"code": "amount_exceeds_authorization", "message": "amount exceeds authorization cap"}
            if auth.get("amount_currency") and body.get("amount_currency") and auth.get("amount_currency") != body.get("amount_currency"):
                return 409, {"code": "currency_mismatch", "message": "currency mismatch"}
            item = dict(body)
            item.setdefault("execution_result_id", self.state.new_id("result"))
            item["id"] = item["execution_result_id"]
            item["authorization_id"] = auth_id
            self.state.collections["external-execution-results"][item["execution_result_id"]] = item
            return 201, item
        if len(parts) == 1 and method == "GET":
            return 200, self._list("external-execution-results", query)
        if len(parts) == 2 and method == "GET":
            return 200, self._get_item("external-execution-results", parts[1])
        raise KeyError("execution result")

    def _aiproofs(self, method, parts, query, body):
        if len(parts) == 2 and parts[1] == "generate" and method == "POST":
            result = self._get_item("external-execution-results", body.get("execution_result_id"))
            proof_hash = hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
            sig = hmac.new(self.state.proof_secret.encode(), proof_hash.encode(), hashlib.sha256).hexdigest()
            proof = {"id": self.state.new_id("proof"), "execution_result_id": result["execution_result_id"], "proof_hash": proof_hash, "signature": sig, "verified": True, "metadata": {"issuer": "mock-compliagl"}}
            self.state.collections["aiproofs"][proof["id"]] = proof
            return 201, proof
        if len(parts) == 1 and method == "GET":
            return 200, self._list("aiproofs", query)
        if len(parts) == 2 and method == "GET":
            return 200, self._get_item("aiproofs", parts[1])
        if len(parts) == 3 and parts[2] == "verify" and method == "GET":
            proof = self._get_item("aiproofs", parts[1])
            expected = hmac.new(self.state.proof_secret.encode(), proof["proof_hash"].encode(), hashlib.sha256).hexdigest()
            return 200, {"proof_id": parts[1], "valid": hmac.compare_digest(proof.get("signature", ""), expected)}
        raise KeyError("aiproof")


class MockCompliAGLServer:
    def __init__(self):
        self.state = MockState()
        handler = type("BoundMockHandler", (MockHandler,), {"state": self.state})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        host, port = self.httpd.server_address
        self.base_url = f"http://{host}:{port}"

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
