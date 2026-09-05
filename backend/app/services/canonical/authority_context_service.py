"""CompliIdentity authority-context client.

Calls CompliIdentity's ``POST /api/v1/tenants/{tenant_id}/authority-context/
{principal_id}`` endpoint (contract ``compliidentity.agl.authority.v1``, see
``docs/architecture/COMPLIAGL_AUTHORITY_CONTRACT.md`` in the CompliIdentity
repo). Only governance packages that declare
``requires_authority_context: true`` trigger a call at all (see
``decision_service.py``); packages that don't declare it are unaffected by
this module's existence.

**No caching.** The contract's own ``cache.max_age_seconds: "0"`` /
no-store, must-revalidate directives are explicit: CompliAGL must call fresh
on every decision, never cache or compare against a local TTL. Staleness is
instead reported *in* the response itself (``current_trust_state`` /
``trust_stale`` / ``trust_absent``) and handled as ordinary
package-authorable facts, same as any other ``authority_for_request.reason``.

Modeled on the one other real external-HTTP-call precedent in this codebase,
``services/evidence/connectors/securerob.py``: explicit constructor
(base URL + service identity + injectable ``httpx.Client`` for tests),
explicit timeout, env-var configuration. Unlike that connector, this client
never raises past its own boundary — every failure mode (network error,
timeout, non-2xx, malformed body) normalizes to a returned ``UNAVAILABLE``
status so the caller has exactly one structural fail-closed check to make,
regardless of *why* the call didn't succeed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import httpx

AuthorityStatus = Literal["OK", "KNOWN_DENIED", "UNAVAILABLE"]

CONTRACT_VERSION = "1"

# Per COMPLIAGL_AUTHORITY_CONTRACT.md's error table: 404 principal_not_found
# is the one HTTP-error-shaped response that is a real, known-bad business
# fact (the principal genuinely doesn't exist), not a system failure. Every
# other non-2xx status in that table -- including 400s that mean "our
# request was malformed" -- is UNAVAILABLE: a structural fail-closed
# condition, never eligible to support an APPROVED decision.
_KNOWN_DENIED_HTTP_STATUS = 404


@dataclass(frozen=True)
class AuthorityContext:
    """Normalized result of one authority-context probe.

    ``status`` is CompliAGL's own three-state classification, not a field
    CompliIdentity returns:

    * ``OK`` -- the call succeeded; ``reason`` / ``sufficient`` / ``active`` /
      ``current_trust_state`` reflect CompliIdentity's own
      ``authority_for_request`` (plus top-level fields) as ordinary
      package-authorable facts -- no interpretation happens here.
    * ``KNOWN_DENIED`` -- CompliIdentity affirmatively reported a real,
      known-bad fact via an HTTP error (currently just 404
      ``principal_not_found``). Also purely package-authorable, same as
      ``OK`` -- this is data, not a client failure.
    * ``UNAVAILABLE`` -- the call failed, timed out, or CompliIdentity itself
      could not evaluate (503 ``context_unevaluable``, the contract's own
      explicit "fail closed" case). Never eligible to support an APPROVED
      decision -- see ``decision_service._resolve_outcome``.
    """

    status: AuthorityStatus
    reason: Optional[str] = None
    sufficient: Optional[bool] = None
    active: Optional[bool] = None
    current_trust_state: Optional[str] = None
    authority_revision: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)


def _unavailable(reason: str, raw: Optional[dict[str, Any]] = None) -> AuthorityContext:
    return AuthorityContext(status="UNAVAILABLE", reason=reason, raw=raw or {})


def _parse_ok(data: dict[str, Any]) -> AuthorityContext:
    authority_for_request = data.get("authority_for_request") or {}
    return AuthorityContext(
        status="OK",
        reason=authority_for_request.get("reason"),
        sufficient=authority_for_request.get("sufficient"),
        active=data.get("active"),
        current_trust_state=data.get("current_trust_state"),
        authority_revision=data.get("authority_revision"),
        raw=data,
    )


def _error_code(error_body: Any) -> Optional[str]:
    if not isinstance(error_body, dict):
        return None
    error = error_body.get("error")
    if isinstance(error, dict):
        return error.get("code")
    return None


class AuthorityContextClient:
    """Client for CompliIdentity's authority-context endpoint.

    Construction is explicit (base URL + CompliAGL's own service-principal
    identity + http client), same injection style as the SecureRob connector,
    so this can be unit tested with a fake transport or a fake client
    entirely (see ``decision_service.py``'s tests).
    """

    def __init__(
        self,
        *,
        base_url: str,
        service_principal_id: str,
        bearer_token: Optional[str] = None,
        timeout_seconds: float = 5.0,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        # CompliAGL authenticating itself to CompliIdentity as the caller --
        # sent as X-Actor-Principal-Id on every call, distinct from
        # principal_id (the subject being asked about) in the URL/fetch()
        # call. Requires a CompliAGL service principal to be bootstrapped in
        # CompliIdentity's IAM -- open item, tracked outside this repo.
        self._service_principal_id = service_principal_id
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds
        self._client = http_client or httpx.Client(
            base_url=self._base_url, timeout=timeout_seconds
        )

    def fetch(
        self,
        *,
        organization_id: str,
        principal_id: str,
        resource: str,
        action: str,
        attribute: Optional[str] = None,
        value: Optional[str] = None,
        environment: Optional[str] = None,
        resource_instance: Optional[str] = None,
    ) -> AuthorityContext:
        """Fetch and normalize authority context for one actor/request pair.

        Never raises: network failure, timeout, and every non-2xx status
        other than 404 all normalize to ``UNAVAILABLE`` so the caller has a
        single structural fail-closed check to make.
        """
        body: dict[str, Any] = {
            "contract_version": CONTRACT_VERSION,
            "resource": resource,
            "action": action,
        }
        if attribute is not None:
            body["attribute"] = attribute
        if value is not None:
            body["value"] = value
        if environment is not None:
            body["environment"] = environment
        if resource_instance is not None:
            body["resource_instance"] = resource_instance

        headers = {
            "X-Tenant-Id": organization_id,
            "X-Actor-Principal-Id": self._service_principal_id,
        }
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"

        try:
            response = self._client.post(
                f"/api/v1/tenants/{organization_id}/authority-context/{principal_id}",
                json=body,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            return _unavailable(f"timeout: {exc}")
        except httpx.HTTPError as exc:
            return _unavailable(f"request_failed: {exc}")

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError as exc:
                return _unavailable(f"malformed_response: {exc}")
            if not isinstance(data, dict):
                return _unavailable("malformed_response: non-object body")
            return _parse_ok(data)

        try:
            error_body = response.json()
        except ValueError:
            error_body = {}

        if response.status_code == _KNOWN_DENIED_HTTP_STATUS:
            return AuthorityContext(
                status="KNOWN_DENIED",
                reason=_error_code(error_body) or "principal_not_found",
                raw=error_body if isinstance(error_body, dict) else {},
            )

        return _unavailable(
            _error_code(error_body) or f"http_{response.status_code}",
            raw=error_body if isinstance(error_body, dict) else {},
        )

    def health_check(self) -> bool:
        """Best-effort reachability probe; never raises."""
        try:
            response = self._client.get("/health", timeout=self._timeout_seconds)
        except httpx.HTTPError:
            return False
        return response.status_code == 200


def default_client(
    *, timeout_seconds: float = 5.0, http_client: Optional[httpx.Client] = None
) -> Optional[AuthorityContextClient]:
    """Build the client from environment configuration.

    Returns ``None`` when the integration isn't configured
    (``COMPLIIDENTITY_BASE_URL`` / ``COMPLIIDENTITY_SERVICE_PRINCIPAL_ID``
    unset). Callers must treat a ``None`` client exactly like an
    ``UNAVAILABLE`` fetch -- never skip the check -- matching the env-var
    configuration pattern in
    ``services/evidence/connectors/production.py``.
    """
    base_url = os.environ.get("COMPLIIDENTITY_BASE_URL")
    service_principal_id = os.environ.get("COMPLIIDENTITY_SERVICE_PRINCIPAL_ID")
    if not base_url or not service_principal_id:
        return None
    return AuthorityContextClient(
        base_url=base_url,
        service_principal_id=service_principal_id,
        bearer_token=os.environ.get("COMPLIIDENTITY_BEARER_TOKEN"),
        timeout_seconds=timeout_seconds,
        http_client=http_client,
    )
