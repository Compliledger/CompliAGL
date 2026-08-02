"""Deterministic connector simulators for the six generic evidence sources.

These simulators implement the generic :class:`EvidenceConnector` interface so
the evidence layer can run end-to-end without external systems. They are
**mock** connectors (``is_mock=True``) and are therefore rejected in production
mode — production deployments register real connectors with the same interface.

Each simulator is driven by a ``fixtures`` mapping so tests can deterministically
control what a source returns (including timeouts, transient failures, missing
evidence, revoked/expired/stale items and binding mismatches). Nothing here is
domain-specific: the connectors are named after generic source types, not after
airlines or payment applications.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

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
    SensitivityClassification,
)
from app.utils.timestamps import utc_now


def _as_datetime(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class SimulatedConnector(EvidenceConnector):
    """A generic, fixture-driven evidence connector simulator.

    ``fixtures`` maps an ``evidence_requirement_id`` (preferred) or an
    ``evidence_type`` to a response specification. A specification supports:

    * ``behavior``: ``collect`` (default), ``timeout``, ``error`` or ``not_found``,
    * ``fail_times``: number of leading attempts that raise a timeout before the
      request finally succeeds (used to exercise the retry policy),
    * any :class:`CollectResult` field (``payload``, ``issuer``, ``issued_at``,
      ``expires_at``, ``signature``, ``signature_valid``, ``revoked``,
      ``subject_id``, ``target_id``, ``intent_id``, ``sensitivity``, ``claims``,
      ``source_authority``).
    """

    def __init__(
        self,
        *,
        connector_id: str,
        source_type: str,
        supported_evidence_types: tuple[str, ...],
        auth_config_reference: Optional[str] = None,
        trusted_issuers: tuple[str, ...] = (),
        is_mock: bool = True,
        timeout_seconds: float = 5.0,
        retry_policy: Optional[RetryPolicy] = None,
        fixtures: Optional[dict[str, dict[str, Any]]] = None,
        healthy: bool = True,
        connection_valid: bool = True,
    ) -> None:
        self.connector_id = connector_id
        self.source_type = source_type
        self.supported_evidence_types = tuple(supported_evidence_types)
        self.auth_config_reference = auth_config_reference
        self.trusted_issuers = tuple(trusted_issuers)
        self.is_mock = is_mock
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.fixtures = dict(fixtures or {})
        self._healthy = healthy
        self._connection_valid = connection_valid
        # Per-requirement attempt counters, so ``fail_times`` can be honoured
        # across the orchestrator's retry loop.
        self._attempts: dict[str, int] = {}

    # -- fixture resolution ---------------------------------------------- #
    def _spec_for(self, request: CollectRequest) -> Optional[dict[str, Any]]:
        if request.evidence_requirement_id in self.fixtures:
            return self.fixtures[request.evidence_requirement_id]
        if request.evidence_type in self.fixtures:
            return self.fixtures[request.evidence_type]
        return None

    # -- interface -------------------------------------------------------- #
    def collect(self, request: CollectRequest) -> CollectResult:
        spec = self._spec_for(request)
        if spec is None:
            # No fixture => the source genuinely has no such evidence. This is a
            # truthful "not found"; the orchestrator never fabricates a payload.
            return CollectResult(
                status=EvidenceCollectionStatus.NOT_FOUND.value,
                payload=None,
                error="no evidence for requirement",
            )

        key = request.evidence_requirement_id
        self._attempts[key] = self._attempts.get(key, 0) + 1
        attempt = self._attempts[key]

        fail_times = int(spec.get("fail_times", 0))
        if attempt <= fail_times:
            raise ConnectorTimeout(
                f"{self.connector_id}: simulated transient timeout "
                f"(attempt {attempt})"
            )

        behavior = spec.get("behavior", "collect")
        if behavior == "timeout":
            raise ConnectorTimeout(f"{self.connector_id}: simulated timeout")
        if behavior == "error":
            raise ConnectorError(
                spec.get("error", f"{self.connector_id}: simulated error")
            )
        if behavior == "not_found":
            return CollectResult(
                status=EvidenceCollectionStatus.NOT_FOUND.value,
                payload=None,
                error="evidence not found at source",
            )

        return CollectResult(
            status=EvidenceCollectionStatus.COLLECTED.value,
            payload=spec.get("payload"),
            payload_reference=spec.get("payload_reference"),
            sensitivity=spec.get(
                "sensitivity", SensitivityClassification.INTERNAL.value
            ),
            issuer=spec.get("issuer"),
            issued_at=_as_datetime(spec.get("issued_at")) or utc_now(),
            expires_at=_as_datetime(spec.get("expires_at")),
            signature=spec.get("signature"),
            signature_valid=spec.get("signature_valid"),
            revoked=bool(spec.get("revoked", False)),
            subject_id=spec.get("subject_id", request.subject_id),
            target_id=spec.get("target_id", request.target_id),
            intent_id=spec.get("intent_id", request.intent_id),
            claims=dict(spec.get("claims", {})),
            source_authority=bool(spec.get("source_authority", True)),
        )

    def health_check(self) -> ConnectorHealth:
        if self._healthy:
            return ConnectorHealth(status=ConnectorHealthStatus.HEALTHY.value)
        return ConnectorHealth(
            status=ConnectorHealthStatus.UNAVAILABLE.value,
            detail="simulated unavailable",
        )

    def validate_connection(self) -> bool:
        return self._connection_valid


# --------------------------------------------------------------------------- #
# Concrete simulator factories — one per generic source type.
# --------------------------------------------------------------------------- #
def governance_registry_connector(**kwargs: Any) -> SimulatedConnector:
    """Simulate the CompliLedger governance-package registry."""
    return SimulatedConnector(
        connector_id=kwargs.pop("connector_id", "sim-governance-registry"),
        source_type=EvidenceSourceType.GOVERNANCE_REGISTRY.value,
        supported_evidence_types=kwargs.pop(
            "supported_evidence_types",
            ("governance_package", "policy_reference", "control_definition"),
        ),
        auth_config_reference=kwargs.pop(
            "auth_config_reference", "authref://governance-registry"
        ),
        trusted_issuers=kwargs.pop("trusted_issuers", ("compliledger.registry",)),
        **kwargs,
    )


def identity_delegation_connector(**kwargs: Any) -> SimulatedConnector:
    """Simulate an internal identity / delegation source."""
    return SimulatedConnector(
        connector_id=kwargs.pop("connector_id", "sim-identity-delegation"),
        source_type=EvidenceSourceType.IDENTITY_PROVIDER.value,
        supported_evidence_types=kwargs.pop(
            "supported_evidence_types",
            ("verified_identity", "delegation", "authorization_grant"),
        ),
        auth_config_reference=kwargs.pop(
            "auth_config_reference", "authref://identity-provider"
        ),
        trusted_issuers=kwargs.pop("trusted_issuers", ("idp.example",)),
        **kwargs,
    )


def external_application_connector(**kwargs: Any) -> SimulatedConnector:
    """Simulate an external merchant or application API."""
    return SimulatedConnector(
        connector_id=kwargs.pop("connector_id", "sim-external-application"),
        source_type=EvidenceSourceType.EXTERNAL_APPLICATION.value,
        supported_evidence_types=kwargs.pop(
            "supported_evidence_types",
            ("vendor_approval", "application_record", "merchant_status"),
        ),
        auth_config_reference=kwargs.pop(
            "auth_config_reference", "authref://external-application"
        ),
        trusted_issuers=kwargs.pop("trusted_issuers", ("procurement.example",)),
        **kwargs,
    )


def account_allowance_connector(**kwargs: Any) -> SimulatedConnector:
    """Simulate a wallet / account / allowance source."""
    return SimulatedConnector(
        connector_id=kwargs.pop("connector_id", "sim-account-allowance"),
        source_type=EvidenceSourceType.ACCOUNT_STATE.value,
        supported_evidence_types=kwargs.pop(
            "supported_evidence_types",
            ("allowance", "account_balance", "spend_limit"),
        ),
        auth_config_reference=kwargs.pop(
            "auth_config_reference", "authref://account-state"
        ),
        trusted_issuers=kwargs.pop("trusted_issuers", ("ledger.example",)),
        **kwargs,
    )


def approval_connector(**kwargs: Any) -> SimulatedConnector:
    """Simulate an approval source."""
    return SimulatedConnector(
        connector_id=kwargs.pop("connector_id", "sim-approval"),
        source_type=EvidenceSourceType.APPROVAL_WORKFLOW.value,
        supported_evidence_types=kwargs.pop(
            "supported_evidence_types",
            ("manager_approval", "approval", "authorization"),
        ),
        auth_config_reference=kwargs.pop(
            "auth_config_reference", "authref://approval-workflow"
        ),
        trusted_issuers=kwargs.pop("trusted_issuers", ("approvals.example",)),
        **kwargs,
    )


def execution_result_connector(**kwargs: Any) -> SimulatedConnector:
    """Simulate an external execution-result source."""
    return SimulatedConnector(
        connector_id=kwargs.pop("connector_id", "sim-execution-result"),
        source_type=EvidenceSourceType.EXECUTION_RESULT.value,
        supported_evidence_types=kwargs.pop(
            "supported_evidence_types",
            ("execution_result", "settlement_receipt", "delivery_confirmation"),
        ),
        auth_config_reference=kwargs.pop(
            "auth_config_reference", "authref://execution-result"
        ),
        trusted_issuers=kwargs.pop("trusted_issuers", ("execution.example",)),
        **kwargs,
    )
