"""Generic evidence connector interface and shared data structures.

The :class:`EvidenceConnector` interface is deliberately **platform-neutral**:
it never assumes the platform is an airline, a payment application, or any other
concrete domain. A connector describes *what kinds of evidence it can serve*
(``supported_evidence_types``) and *what authoritative source it represents*
(``source_type``); a deployment maps its real systems onto these generic
concepts.

Every connector supports:

* a stable ``connector_id``,
* the set of ``supported_evidence_types`` it can serve,
* its ``source_type`` (see :class:`~app.utils.canonical_enums.EvidenceSourceType`),
* an ``auth_config_reference`` — an *indirect* reference to authentication
  configuration (never inline secrets),
* :meth:`collect` — collect evidence for a single request,
* :meth:`health_check` — report health without side effects,
* :meth:`validate_connection` — confirm the source is reachable/authorized,
* an explicit ``timeout`` and a ``retry_policy``.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.utils.canonical_enums import (
    ConnectorHealthStatus,
    EvidenceCollectionStatus,
    SensitivityClassification,
)


class ConnectorTimeout(Exception):
    """Raised by a connector (or simulator) to signal a collection timeout."""


class ConnectorError(Exception):
    """Raised by a connector to signal a non-timeout collection failure."""


@dataclass(frozen=True)
class RetryPolicy:
    """Deterministic retry policy for a connector.

    ``backoff_seconds`` is advisory; the orchestrator keeps it at ``0`` in tests
    for determinism. ``max_attempts`` is the total number of attempts (>= 1).
    """

    max_attempts: int = 3
    backoff_seconds: float = 0.0
    retry_on_timeout: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": int(self.max_attempts),
            "backoff_seconds": float(self.backoff_seconds),
            "retry_on_timeout": bool(self.retry_on_timeout),
        }


@dataclass
class CollectRequest:
    """A single, connector-agnostic evidence collection request.

    Built by the orchestrator from one resolved evidence requirement plus the
    runtime subject/target/intent bindings.
    """

    evidence_requirement_id: str
    evidence_type: str
    source_type: str
    subject_id: Optional[str] = None
    target_id: Optional[str] = None
    intent_id: Optional[str] = None
    allowed_issuers: list[str] = field(default_factory=list)
    freshness_threshold: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectResult:
    """The connector's answer for one :class:`CollectRequest`.

    A connector reports what it *actually* observed. It must not guess or
    fabricate: if it has no evidence it returns ``status=NOT_FOUND`` with an
    empty payload. Binding fields (``subject_id`` / ``target_id`` / ``intent_id``)
    reflect the subject/target/intent the evidence really attests to, which the
    validator compares against the request.
    """

    status: str = EvidenceCollectionStatus.COLLECTED.value
    payload: Optional[dict[str, Any]] = None
    # Opaque reference to a payload held in a secure store (used when the payload
    # itself is too sensitive to move through the runtime).
    payload_reference: Optional[str] = None
    sensitivity: str = SensitivityClassification.INTERNAL.value
    issuer: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    signature: Optional[str] = None
    # Tri-state: True/False when a signature is present, None when N/A.
    signature_valid: Optional[bool] = None
    revoked: bool = False
    subject_id: Optional[str] = None
    target_id: Optional[str] = None
    intent_id: Optional[str] = None
    # Structured, source-specific claims used by normalization.
    claims: dict[str, Any] = field(default_factory=dict)
    # Whether the connector's source is authoritative for the evidence type.
    source_authority: bool = True
    error: Optional[str] = None


@dataclass(frozen=True)
class ConnectorHealth:
    """Health report returned by :meth:`EvidenceConnector.health_check`."""

    status: str = ConnectorHealthStatus.HEALTHY.value
    detail: Optional[str] = None


class EvidenceConnector(abc.ABC):
    """Abstract, platform-neutral evidence connector interface."""

    #: Stable, unique connector identifier.
    connector_id: str
    #: The generic authoritative source this connector represents.
    source_type: str
    #: Evidence types this connector can serve.
    supported_evidence_types: tuple[str, ...]
    #: Indirect reference to authentication config (never inline secrets).
    auth_config_reference: Optional[str] = None
    #: True for simulators / mock connectors — rejected in production mode.
    is_mock: bool = False
    #: Issuers this source is trusted to attest for.
    trusted_issuers: tuple[str, ...] = ()
    #: Per-call timeout, in seconds.
    timeout_seconds: float = 5.0
    #: Retry policy applied by the orchestrator.
    retry_policy: RetryPolicy = RetryPolicy()

    # -- capability ------------------------------------------------------- #
    def supports(self, evidence_type: Optional[str]) -> bool:
        """Return True when this connector can serve ``evidence_type``."""
        if evidence_type is None:
            return False
        return evidence_type in self.supported_evidence_types

    def describe(self) -> dict[str, Any]:
        """Return a registry-friendly description of this connector."""
        return {
            "connector_id": self.connector_id,
            "source_type": self.source_type,
            "supported_evidence_types": list(self.supported_evidence_types),
            "auth_config_reference": self.auth_config_reference,
            "is_mock": bool(self.is_mock),
            "trusted_issuers": list(self.trusted_issuers),
            "timeout_seconds": float(self.timeout_seconds),
            "retry_policy": self.retry_policy.as_dict(),
        }

    # -- interface -------------------------------------------------------- #
    @abc.abstractmethod
    def collect(self, request: CollectRequest) -> CollectResult:
        """Collect evidence for a single request.

        Implementations must raise :class:`ConnectorTimeout` on timeout and
        :class:`ConnectorError` on a non-timeout failure so the orchestrator can
        apply the retry policy and record the failure explicitly.
        """

    @abc.abstractmethod
    def health_check(self) -> ConnectorHealth:
        """Return the connector's current health without side effects."""

    @abc.abstractmethod
    def validate_connection(self) -> bool:
        """Return True when the source is reachable and the auth config valid."""
