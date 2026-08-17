"""Real (non-mock) evidence connector for SecureRob perception facts.

Unlike the fixture-driven simulators in ``simulators.py``, this connector
calls a real system: the CompliAGL Execution Gateway's evidence endpoint
(``GET /api/v1/evidence/executions/{execution_id}/perception``). It never
computes or influences a governance decision -- it only fetches, and
faithfully reports, the perception facts the Gateway already captured for
a given execution, so CompliAGL's own control evaluation can treat them as
validated evidence rather than an unverified assertion.

See docs/securerob-evidence-connector-spec.md in the Gateway repo for the
full design and the open questions still needing confirmation (marked
inline below with TODO).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx

from app.services.evidence.connectors.base import (
    CollectRequest,
    CollectResult,
    ConnectorError,
    ConnectorHealth,
    ConnectorTimeout,
    EvidenceConnector,
    RetryPolicy,
)
from app.utils.canonical_enums import ConnectorHealthStatus, EvidenceCollectionStatus, EvidenceSourceType

# The evidence_type this connector serves. Must match the evidence_type in
# the SecureRob governance package's evidence_requirements
# (EV-SECUREROB-PERCEPTION -> "securerob.perception_snapshot").
SECUREROB_PERCEPTION_EVIDENCE_TYPE = "securerob.perception_snapshot"

# TODO(open question, see spec doc item 1): EvidenceSourceType has exactly
# six fixed values, none of which literally describe "device telemetry."
# EXTERNAL_APPLICATION is used here as the closest honest fit -- the
# Gateway genuinely is an external application from CompliAGL's
# perspective. Please confirm this is acceptable, or advise if a new enum
# value should be added instead.
SECUREROB_SOURCE_TYPE = EvidenceSourceType.EXTERNAL_APPLICATION.value

# Must match the "issuer" field the Gateway's evidence endpoint returns
# (see app/api/routes/evidence.py, GATEWAY_EVIDENCE_ISSUER, in the Gateway
# repo) so trusted_issuers below actually matches at runtime.
GATEWAY_ISSUER_ID = "compliagl-execution-gateway"


class SecureRobPerceptionConnector(EvidenceConnector):
    """Real evidence connector: fetches captured perception facts from the
    CompliAGL Execution Gateway for one execution.

    Construction is explicit (base URL + bearer token + http client), same
    injection style as the simulators' constructors, so this can be unit
    tested with a fake transport exactly like the rest of the evidence
    layer's test suite already does for simulators.
    """

    def __init__(
        self,
        *,
        gateway_base_url: str,
        bearer_token: str,
        connector_id: str = "securerob-perception-gateway",
        auth_config_reference: Optional[str] = "authref://securerob-gateway-bearer-token",
        timeout_seconds: float = 5.0,
        retry_policy: Optional[RetryPolicy] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.connector_id = connector_id
        self.source_type = SECUREROB_SOURCE_TYPE
        self.supported_evidence_types = (SECUREROB_PERCEPTION_EVIDENCE_TYPE,)
        self.auth_config_reference = auth_config_reference
        # Real connector: never a simulator, never rejected in production.
        self.is_mock = False
        self.trusted_issuers = (GATEWAY_ISSUER_ID,)
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=3, backoff_seconds=0.5)

        self._base_url = gateway_base_url.rstrip("/")
        self._bearer_token = bearer_token
        # Allow injection of a pre-configured client (e.g. httpx.MockTransport)
        # for tests; otherwise build a real one against gateway_base_url.
        self._client = http_client or httpx.Client(
            base_url=self._base_url, timeout=self.timeout_seconds
        )

    # -- interface -------------------------------------------------------- #
    def collect(self, request: CollectRequest) -> CollectResult:
        """Fetch the Gateway's captured perception facts for this request.

        Confirmed empirically (2026-08-16): CompliAGL's orchestrator does
        NOT populate an execution_id anywhere on CollectRequest -- it has no
        concept of a Gateway execution at all. It does provide intent_id,
        which the Gateway's /executions/by-intent/{intent_id}/perception
        endpoint resolves to the matching execution's captured facts.
        """
        intent_id = request.intent_id
        if not intent_id:
            return CollectResult(
                status=EvidenceCollectionStatus.NOT_FOUND.value,
                payload=None,
                error=(
                    "no intent_id available on CollectRequest; cannot "
                    "resolve which Gateway execution to query"
                ),
            )

        try:
            response = self._client.get(
                f"/api/v1/evidence/executions/by-intent/{intent_id}/perception",
                headers={"Authorization": f"Bearer {self._bearer_token}"},
            )
        except httpx.TimeoutException as exc:
            raise ConnectorTimeout(f"{self.connector_id}: Gateway request timed out") from exc
        except httpx.HTTPError as exc:
            raise ConnectorError(f"{self.connector_id}: Gateway request failed: {exc}") from exc

        if response.status_code == 404:
            return CollectResult(
                status=EvidenceCollectionStatus.NOT_FOUND.value,
                payload=None,
                error=f"no perception evidence found for intent {intent_id}",
            )
        if response.status_code == 401:
            raise ConnectorError(f"{self.connector_id}: Gateway rejected the bearer token (401)")
        if response.status_code >= 500:
            raise ConnectorError(
                f"{self.connector_id}: Gateway returned {response.status_code}"
            )
        if response.status_code != 200:
            raise ConnectorError(
                f"{self.connector_id}: unexpected Gateway status {response.status_code}: "
                f"{response.text}"
            )

        data: dict[str, Any] = response.json()
        issued_at = _parse_datetime(data.get("issued_at"))

        # This connector deliberately never signs or fabricates integrity
        # metadata the Gateway didn't actually provide. The Gateway's
        # evidence endpoint does not currently produce a cryptographic
        # signature (see spec doc item 5) -- signature/signature_valid are
        # left None, honestly, rather than defaulted to something implying
        # verification that never happened.
        return CollectResult(
            status=EvidenceCollectionStatus.COLLECTED.value,
            payload=data.get("claims"),
            claims=dict(data.get("claims") or {}),
            issuer=data.get("issuer"),
            issued_at=issued_at,
            expires_at=None,
            signature=None,
            signature_valid=None,
            revoked=False,
            subject_id=None,
            target_id=data.get("target_id"),
            intent_id=data.get("intent_id"),
            source_authority=True,
        )

    def health_check(self) -> ConnectorHealth:
        """Check the Gateway's unauthenticated /health endpoint."""
        try:
            response = self._client.get("/health", timeout=self.timeout_seconds)
        except httpx.HTTPError as exc:
            return ConnectorHealth(
                status=ConnectorHealthStatus.UNAVAILABLE.value,
                detail=f"Gateway unreachable: {exc}",
            )
        if response.status_code == 200:
            return ConnectorHealth(status=ConnectorHealthStatus.HEALTHY.value)
        return ConnectorHealth(
            status=ConnectorHealthStatus.UNAVAILABLE.value,
            detail=f"Gateway /health returned {response.status_code}",
        )

    def validate_connection(self) -> bool:
        """Confirm the configured bearer token is actually accepted.

        Uses a deliberately-invalid execution_id: a 401 means the token is
        bad (invalid connection); a 404 means the token was accepted and the
        Gateway correctly reports the execution doesn't exist (valid
        connection, expected outcome for a random id).
        """
        try:
            response = self._client.get(
                "/api/v1/evidence/executions/00000000-0000-0000-0000-000000000000/perception",
                headers={"Authorization": f"Bearer {self._bearer_token}"},
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError:
            return False
        return response.status_code in (200, 404)


def securerob_perception_connector(
    *, gateway_base_url: str, bearer_token: str, **kwargs: Any
) -> SecureRobPerceptionConnector:
    """Factory matching the style of simulators.py's factory functions --
    for use wherever the production ConnectorRegistry is assembled (see
    connectors/__init__.py's default_simulator_registry() for the pattern;
    this is the production equivalent for SecureRob perception evidence).
    """
    return SecureRobPerceptionConnector(
        gateway_base_url=gateway_base_url, bearer_token=bearer_token, **kwargs
    )


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
