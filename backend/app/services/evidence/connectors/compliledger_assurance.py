"""Real (non-mock) evidence connector for CompliLedger's continuous-assurance state.

Calls the CompliLedger `GET /api/v1/assurance/state` endpoint (Circle Grant
MVP PR 2 -- see docs/circle-mvp-implementation-plan.md) for a single fixed
target/control pair. It never interprets what CompliLedger reports -- healthy
or degraded, it faithfully passes the claim through -- so the Circle treasury
governance package's decision conditions (not this connector, and not the
control's own evaluation_expression) are the only place assurance content is
judged. See docs/dev-rules.md rule 4.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
from app.utils.canonical_enums import (
    ConnectorHealthStatus,
    EvidenceCollectionStatus,
    EvidenceSourceType,
)

# Must match the evidence_type in the Circle treasury governance package's
# evidence_requirements (EV-CIRCLE-LUSD-ASSURANCE -> "compliledger.assurance_state.v1").
CIRCLE_ASSURANCE_EVIDENCE_TYPE = "compliledger.assurance_state.v1"

CIRCLE_ASSURANCE_SOURCE_TYPE = EvidenceSourceType.EXTERNAL_APPLICATION.value

# Must match the trusted_issuers / allowed_issuers wired into the Circle
# treasury governance package's evidence requirement.
CIRCLE_ASSURANCE_ISSUER = "compliledger.assurance-state"

# Fixed MVP scope: the GENIUS LUSD reserve control, per the assurance/state
# contract in docs/circle-mvp-implementation-plan.md PR 2.
CIRCLE_TARGET_ID = "target_lusd"
CIRCLE_CONTROL_ID = "GENIUS-LUSD-RESERVE-001"


class CompliLedgerAssuranceConnector(EvidenceConnector):
    """Real evidence connector: fetches live continuous-assurance state from
    CompliLedger for the GENIUS LUSD reserve control.

    Construction is explicit (base URL + http client), same injection style as
    ``securerob.py``, so this can be unit tested with a fake transport.
    """

    def __init__(
        self,
        *,
        base_url: str,
        connector_id: str = "compliledger-assurance-state",
        timeout_seconds: float = 5.0,
        retry_policy: Optional[RetryPolicy] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.connector_id = connector_id
        self.source_type = CIRCLE_ASSURANCE_SOURCE_TYPE
        self.supported_evidence_types = (CIRCLE_ASSURANCE_EVIDENCE_TYPE,)
        self.auth_config_reference = None
        # Real connector: never a simulator, never rejected in production.
        self.is_mock = False
        self.trusted_issuers = (CIRCLE_ASSURANCE_ISSUER,)
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=3, backoff_seconds=0.5)

        self._base_url = base_url.rstrip("/")
        # Allow injection of a pre-configured client (e.g. httpx.MockTransport)
        # for tests; otherwise build a real one against base_url.
        self._client = http_client or httpx.Client(
            base_url=self._base_url, timeout=self.timeout_seconds
        )

    # -- interface -------------------------------------------------------- #
    def collect(self, request: CollectRequest) -> CollectResult:
        """Fetch CompliLedger's current assurance state for the fixed
        target/control pair. Never raises past this boundary except the two
        typed connector exceptions (per docs/dev-rules.md rule 5) -- any
        other failure normalizes to missing evidence via those exceptions and
        the orchestrator's retry/exhaustion path.
        """
        try:
            response = self._client.get(
                "/api/v1/assurance/state",
                params={"target_id": CIRCLE_TARGET_ID, "control_ids": CIRCLE_CONTROL_ID},
            )
        except httpx.TimeoutException as exc:
            raise ConnectorTimeout(
                f"{self.connector_id}: CompliLedger request timed out"
            ) from exc
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"{self.connector_id}: CompliLedger request failed: {exc}"
            ) from exc

        if response.status_code >= 500:
            raise ConnectorError(
                f"{self.connector_id}: CompliLedger returned {response.status_code}"
            )
        if response.status_code != 200:
            raise ConnectorError(
                f"{self.connector_id}: unexpected CompliLedger status "
                f"{response.status_code}: {response.text}"
            )

        data: dict[str, Any] = response.json()
        controls = data.get("controls") or []
        control = next(
            (c for c in controls if isinstance(c, dict) and c.get("control_id") == CIRCLE_CONTROL_ID),
            None,
        )
        if control is None:
            return CollectResult(
                status=EvidenceCollectionStatus.NOT_FOUND.value,
                payload=None,
                error=(
                    f"CompliLedger assurance/state response did not include "
                    f"control {CIRCLE_CONTROL_ID!r}"
                ),
            )

        # Copied verbatim from CompliLedger's response -- never interpreted
        # or fabricated. A healthy claim and a degraded claim are equally
        # "well-formed"; only the governance package's decision conditions
        # judge the content.
        claims = {
            "target_id": data.get("target_id"),
            "control_id": control.get("control_id"),
            "applicability": control.get("applicability"),
            "result": control.get("result"),
            "evidence_sufficiency": control.get("evidence_sufficiency"),
            "evidence_freshness": control.get("evidence_freshness"),
            "monitoring_status": control.get("monitoring_status"),
            "assessment_id": control.get("assessment_id"),
            "decision_id": control.get("decision_id"),
            "proof_id": control.get("proof_id"),
            "proof_hash": control.get("proof_hash"),
            "proof_status": control.get("proof_status"),
            "last_evaluated_at": control.get("last_evaluated_at"),
        }

        return CollectResult(
            status=EvidenceCollectionStatus.COLLECTED.value,
            payload=claims,
            claims=claims,
            issuer=CIRCLE_ASSURANCE_ISSUER,
            issued_at=datetime.now(timezone.utc),
            expires_at=None,
            # This connector never signs or fabricates integrity metadata
            # CompliLedger didn't actually provide -- left honestly None,
            # same rule securerob.py follows.
            signature=None,
            signature_valid=None,
            revoked=False,
            subject_id=None,
            target_id=data.get("target_id"),
            intent_id=request.intent_id,
            source_authority=True,
        )

    def health_check(self) -> ConnectorHealth:
        """CompliLedger has no documented /health for this contract; use the
        real assurance/state call itself -- any response means the service is
        reachable, a network error means it isn't.
        """
        try:
            response = self._client.get(
                "/api/v1/assurance/state",
                params={"target_id": CIRCLE_TARGET_ID, "control_ids": CIRCLE_CONTROL_ID},
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            return ConnectorHealth(
                status=ConnectorHealthStatus.UNAVAILABLE.value,
                detail=f"CompliLedger unreachable: {exc}",
            )
        if response.status_code < 500:
            return ConnectorHealth(status=ConnectorHealthStatus.HEALTHY.value)
        return ConnectorHealth(
            status=ConnectorHealthStatus.UNAVAILABLE.value,
            detail=f"CompliLedger assurance/state returned {response.status_code}",
        )

    def validate_connection(self) -> bool:
        try:
            response = self._client.get(
                "/api/v1/assurance/state",
                params={"target_id": CIRCLE_TARGET_ID, "control_ids": CIRCLE_CONTROL_ID},
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError:
            return False
        return response.status_code < 500


def compliledger_assurance_connector(
    *, base_url: str, **kwargs: Any
) -> CompliLedgerAssuranceConnector:
    """Factory matching the style of the other production connector factories."""
    return CompliLedgerAssuranceConnector(base_url=base_url, **kwargs)
