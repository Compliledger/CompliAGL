"""Evidence connector registry.

The registry is the runtime authority on which connectors are available and,
for a given evidence requirement, which connector is the *authoritative* source.
Selection is deterministic: a connector must (a) match the requirement's allowed
source type and (b) declare support for the required evidence type. Ties are
broken by preferring a non-mock connector, then by ``connector_id`` order.

A registry can be built from the built-in simulators (for local development and
tests) or assembled from real connectors in production. The orchestrator accepts
an explicit registry so callers control exactly which connectors are used.
"""

from __future__ import annotations

from typing import Iterable, Optional

from app.services.evidence.connectors import simulators
from app.services.evidence.connectors.base import EvidenceConnector


class ConnectorRegistry:
    """A deterministic, in-memory registry of evidence connectors."""

    def __init__(self, connectors: Optional[Iterable[EvidenceConnector]] = None):
        self._by_id: dict[str, EvidenceConnector] = {}
        for connector in connectors or ():
            self.register(connector)

    # -- mutation --------------------------------------------------------- #
    def register(self, connector: EvidenceConnector) -> None:
        if connector.connector_id in self._by_id:
            raise ValueError(
                f"connector_id already registered: {connector.connector_id}"
            )
        self._by_id[connector.connector_id] = connector

    # -- reads ------------------------------------------------------------ #
    def all(self) -> list[EvidenceConnector]:
        return [self._by_id[k] for k in sorted(self._by_id)]

    def get(self, connector_id: str) -> Optional[EvidenceConnector]:
        return self._by_id.get(connector_id)

    def candidates(
        self, source_type: Optional[str], evidence_type: Optional[str]
    ) -> list[EvidenceConnector]:
        """Return connectors that can authoritatively serve the requirement.

        A candidate must match ``source_type`` (when one is required) and must
        support ``evidence_type``. Results are ordered deterministically with
        non-mock connectors preferred.
        """
        matches = [
            c
            for c in self._by_id.values()
            if (source_type is None or c.source_type == source_type)
            and c.supports(evidence_type)
        ]
        matches.sort(key=lambda c: (c.is_mock, c.connector_id))
        return matches

    def select_authoritative(
        self, source_type: Optional[str], evidence_type: Optional[str]
    ) -> Optional[EvidenceConnector]:
        """Return the single authoritative connector, or ``None`` if there is none."""
        candidates = self.candidates(source_type, evidence_type)
        return candidates[0] if candidates else None


def default_simulator_registry() -> ConnectorRegistry:
    """Return a registry populated with the six built-in mock simulators."""
    return ConnectorRegistry(
        [
            simulators.governance_registry_connector(),
            simulators.identity_delegation_connector(),
            simulators.external_application_connector(),
            simulators.account_allowance_connector(),
            simulators.approval_connector(),
            simulators.execution_result_connector(),
        ]
    )
