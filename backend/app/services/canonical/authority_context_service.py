"""CompliIdentity authority-context client.

Calls CompliIdentity's ``POST /api/v1/tenants/{tenant_id}/authority-context/
{principal_id}`` endpoint (contract ``compliidentity.agl.authority.v1``, see
``docs/architecture/COMPLIAGL_AUTHORITY_CONTRACT.md`` in the CompliIdentity
repo). Only governance packages that declare
``requires_authority_context: true`` trigger a call at all (see
``decision_service.py``); packages that don't declare it are unaffected by
this module's existence.

**No caching.** The contract's own ``cache.max_age_seconds: 0`` /
no-store, must-revalidate directives are explicit: CompliAGL must call fresh
on every decision, never cache or compare against a local TTL. Staleness is
instead reported *in* the response itself (``current_trust_state`` plus the
``trust_absent`` / ``trust_refresh_required`` findings) and handled as
ordinary package-authorable facts, same as any other
``authority_for_request`` signal.

**``authority_for_request`` real shape** (confirmed against 13 live
authority-context responses captured in CompliIdentity's demo3 acceptance
run -- see ``docs/COMPLIIDENTITY_CONTRACT_VOCABULARY_CONFIRMED.md``):
CompliIdentity emits ``sufficient`` / ``permission_present`` /
``limit_exceeded`` / ``approval_required`` booleans plus ``findings`` -- a
mixed list of positive (``permission_present``), informational
(``trust_absent``, ``trust_refresh_required`` -- present on *every*
response) and negative (``permission_missing``, ``delegation_revoked``,
``principal_not_active``, ``resource_scope_unmatched``) codes. There is **no
singular ``reason`` key**. :func:`_derive_reason` collapses these into the
one code a package condition authored against ``authority.reason`` needs;
the raw list is preserved on ``AuthorityContext.findings``.

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

    * ``OK`` -- the call succeeded; the fact fields below reflect
      CompliIdentity's own ``authority_for_request`` (plus top-level fields)
      as ordinary package-authorable facts. The only interpretation applied
      is :func:`_derive_reason` collapsing ``findings`` + the explicit
      booleans into ``reason`` -- ``findings`` itself is passed through raw.
    * ``KNOWN_DENIED`` -- CompliIdentity affirmatively reported a real,
      known-bad fact via an HTTP error (currently just 404
      ``principal_not_found``). Also purely package-authorable, same as
      ``OK`` -- this is data, not a client failure.
    * ``UNAVAILABLE`` -- the call failed, timed out, or CompliIdentity itself
      could not evaluate (503 ``context_unevaluable``, the contract's own
      explicit "fail closed" case). Never eligible to support an APPROVED
      decision -- see ``decision_service._resolve_outcome``.

    Fact fields:

    * ``reason`` -- derived single code (see :func:`_derive_reason`); ``None``
      when nothing actionable was reported.
    * ``sufficient`` / ``permission_present`` / ``approval_required`` /
      ``limit_exceeded`` -- CompliIdentity's ``authority_for_request``
      booleans, verbatim.
    * ``findings`` -- the raw ``authority_for_request.findings`` list, for
      conditions that need the full (positive + informational + negative)
      picture rather than the derived ``reason``.
    * ``active`` -- top-level principal-active flag.
    * ``current_trust_state`` -- the continuous-trust-loop state object
      (``{present, fail_closed, stale, refresh_required, reason_codes, ...}``);
      informational only, the decision engine does not gate on it.
    * ``authority_revision`` -- CompliIdentity's content-revision fingerprint.
    * ``integrity_content_hash`` -- CompliIdentity's own ed25519-signed
      content hash of the response (``integrity.content_hash``); a stronger
      audit anchor than ``authority_revision`` alone. (``proof_ref`` is
      ``null`` on every real response -- ``integrity`` is the real proof
      block.)
    """

    status: AuthorityStatus
    reason: Optional[str] = None
    sufficient: Optional[bool] = None
    active: Optional[bool] = None
    permission_present: Optional[bool] = None
    approval_required: Optional[bool] = None
    limit_exceeded: Optional[bool] = None
    findings: tuple[str, ...] = ()
    # ``authority_for_request.applicable_approvals`` verbatim: the approval
    # requirement(s) CompliIdentity says apply to this request, each an object
    # like ``{"resource", "action", "attribute", "threshold",
    # "approver_principal_type", ...}``. Populated on the *escalating actor's*
    # probe (e.g. a propose over threshold) -- names which principal type must
    # approve. See docs/COMPLIIDENTITY_CONTRACT_VOCABULARY_CONFIRMED.md.
    applicable_approvals: tuple[dict[str, Any], ...] = ()
    current_trust_state: Optional[dict[str, Any]] = None
    authority_revision: Optional[str] = None
    integrity_content_hash: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)


def _unavailable(reason: str, raw: Optional[dict[str, Any]] = None) -> AuthorityContext:
    return AuthorityContext(status="UNAVAILABLE", reason=reason, raw=raw or {})


# Findings in ``authority_for_request.findings`` that represent a positively
# reported "the answer is no" -- as opposed to the informational findings
# CompliIdentity emits on every response regardless of outcome
# (``permission_present``, ``trust_absent``, ``trust_refresh_required``).
# Ordered most-specific-first: when several are present at once (e.g.
# ``["permission_missing", "delegation_revoked"]`` after an explicit
# delegation revoke) the earlier entry is the reported ``reason``. Every
# entry here is DENIED-worthy; ``approval_required`` (ESCALATED-worthy) is
# deliberately checked only *after* none of these match, so a hard denial can
# never be masked into an escalation. Vocabulary confirmed against 13 live
# responses -- see docs/COMPLIIDENTITY_CONTRACT_VOCABULARY_CONFIRMED.md.
_DENIAL_FINDINGS: tuple[str, ...] = (
    "principal_not_active",
    "delegation_revoked",
    "resource_scope_unmatched",
    "permission_missing",
)


def _derive_reason(authority_for_request: dict[str, Any]) -> Optional[str]:
    """Collapse CompliIdentity's ``authority_for_request`` signals into the
    single ``reason`` code package conditions authored against
    ``authority.reason`` expect.

    CompliIdentity emits no singular ``reason`` key -- it emits ``findings``
    (a mixed list) plus the ``limit_exceeded`` / ``approval_required``
    booleans. Returns ``None`` when nothing actionable was reported (the
    happy path, whose ``findings`` still contains ``permission_present`` /
    ``trust_absent`` / ``trust_refresh_required``). The raw list stays on
    ``AuthorityContext.findings`` for conditions that need it.
    """
    findings = authority_for_request.get("findings") or []
    for code in _DENIAL_FINDINGS:
        if code in findings:
            return code
    if authority_for_request.get("limit_exceeded") is True:
        return "limit_exceeded"
    if (
        authority_for_request.get("approval_required") is True
        or "approval_required" in findings
    ):
        return "approval_required"
    return None


def _parse_ok(data: dict[str, Any]) -> AuthorityContext:
    authority_for_request = data.get("authority_for_request") or {}
    findings = authority_for_request.get("findings") or []
    trust_state = data.get("current_trust_state")
    integrity = data.get("integrity")
    return AuthorityContext(
        status="OK",
        reason=_derive_reason(authority_for_request),
        sufficient=authority_for_request.get("sufficient"),
        active=data.get("active"),
        permission_present=authority_for_request.get("permission_present"),
        approval_required=authority_for_request.get("approval_required"),
        limit_exceeded=authority_for_request.get("limit_exceeded"),
        findings=tuple(f for f in findings if isinstance(f, str)),
        applicable_approvals=tuple(
            a
            for a in (authority_for_request.get("applicable_approvals") or [])
            if isinstance(a, dict)
        ),
        current_trust_state=trust_state if isinstance(trust_state, dict) else None,
        authority_revision=data.get("authority_revision"),
        integrity_content_hash=(
            integrity.get("content_hash") if isinstance(integrity, dict) else None
        ),
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


# --------------------------------------------------------------------------- #
# Approver verification (shared by escalation-approval + package approval)
# --------------------------------------------------------------------------- #
_APPROVER_TYPE_HUMAN = "HUMAN"


@dataclass(frozen=True)
class ApproverVerification:
    """Verdict on whether a principal may *approve* a given action right now.

    ``authorized`` is the only field a caller must gate on; the rest is the
    evidence trail. ``reason`` is ``"authorized"`` on success, else a machine
    code: ``client_unconfigured`` / ``authority_unavailable`` /
    ``authority_known_denied`` / ``not_sufficient`` / ``approver_not_human``.
    """

    authorized: bool
    reason: str
    approver_principal_type: Optional[str]
    context: AuthorityContext


def verify_approver_authority(
    client: Optional[AuthorityContextClient],
    *,
    organization_id: str,
    approver_principal_id: str,
    resource: str,
    action: str = "approve",
    resource_instance: Optional[str] = None,
    attribute: Optional[str] = None,
    value: Optional[str] = None,
) -> ApproverVerification:
    """Verify -- against CompliIdentity, at call time -- that
    ``approver_principal_id`` may ``action`` (default ``"approve"``)
    ``resource`` (optionally scoped to ``resource_instance`` / an amount).

    Fail closed on every uncertain path: a ``None`` client, an ``UNAVAILABLE``
    or ``KNOWN_DENIED`` authority context, ``sufficient`` not ``True``, or an
    approver whose own principal type is not ``HUMAN``.

    **Not yet checked here:** that this principal is the approver type
    CompliIdentity itself *requires* for the escalated action. That
    declaration (``authority_for_request.applicable_approvals[].
    approver_principal_type``) lives on the escalating *actor's* decision-time
    probe, not on the approver's ``approve`` probe (confirmed against the
    captured demo3 responses -- an ``approve`` probe returns
    ``applicable_approvals: []``). The real cross-check is done in
    ``escalation_approval_service`` against a required-approver-type persisted
    on the Decision at decision time; ``sufficient == true`` here is still
    CompliIdentity's authoritative "this principal may perform this action".
    """
    if client is None:
        return ApproverVerification(
            False,
            "client_unconfigured",
            None,
            AuthorityContext(status="UNAVAILABLE", reason="not_configured"),
        )

    ctx = client.fetch(
        organization_id=organization_id,
        principal_id=approver_principal_id,
        resource=resource,
        action=action,
        resource_instance=resource_instance,
        attribute=attribute,
        value=value,
    )
    if ctx.status == "UNAVAILABLE":
        return ApproverVerification(False, "authority_unavailable", None, ctx)
    if ctx.status == "KNOWN_DENIED":
        return ApproverVerification(False, "authority_known_denied", None, ctx)

    raw = ctx.raw or {}
    approver_type = raw.get("principal_type") or (
        raw.get("principal") or {}
    ).get("principal_type")

    if ctx.sufficient is not True:
        return ApproverVerification(False, "not_sufficient", approver_type, ctx)

    # Defense in depth beyond `sufficient`: the approver must actually be a
    # HUMAN principal, not an agent or service that merely holds an approve
    # grant. (This confirms the *kind* of principal, not that CompliIdentity's
    # approval-threshold logic named this principal -- see docstring.)
    if approver_type != _APPROVER_TYPE_HUMAN:
        return ApproverVerification(
            False, "approver_not_human", approver_type, ctx
        )

    return ApproverVerification(True, "authorized", approver_type, ctx)
