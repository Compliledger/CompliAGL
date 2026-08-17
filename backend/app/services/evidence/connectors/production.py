"""Production connector registry -- extends the simulator set with real,
non-mock connectors where they exist.

This is deliberately additive: evidence types that don't yet have a real
connector still fall back to their simulator (so nothing else regresses),
but evidence types that DO have a real connector -- currently just
SecureRob perception facts -- get the real one instead.

Configuration is read from environment variables, matching the pattern the
codebase already uses elsewhere for config (adjust if this project uses a
different settings mechanism -- this file was written without direct
visibility into the real config system, see the note in
docs/securerob-evidence-connector-spec.md in the Gateway repo).
"""

from __future__ import annotations

import os

from app.services.evidence.connectors import ConnectorRegistry, simulators
from app.services.evidence.connectors.securerob import securerob_perception_connector


def default_production_registry() -> ConnectorRegistry:
    """Return the registry actually used for production evidence collection:
    simulators for anything without a real connector yet, plus real
    connectors where they exist.
    """
    connectors = [
        simulators.governance_registry_connector(),
        simulators.identity_delegation_connector(),
        simulators.external_application_connector(),
        simulators.account_allowance_connector(),
        simulators.approval_connector(),
        simulators.execution_result_connector(),
    ]

    gateway_base_url = os.environ.get("SECUREROB_GATEWAY_BASE_URL")
    gateway_bearer_token = os.environ.get("SECUREROB_GATEWAY_BEARER_TOKEN")
    if gateway_base_url and gateway_bearer_token:
        connectors.append(
            securerob_perception_connector(
                gateway_base_url=gateway_base_url,
                bearer_token=gateway_bearer_token,
            )
        )
    # If the env vars aren't set, the SecureRob evidence type simply has no
    # authoritative connector yet -- collection will correctly report
    # EVIDENCE_COLLECTION_FAILED / HAS_UNRESOLVED rather than silently using
    # a mock in production, since is_mock connectors are already rejected in
    # production mode by the orchestrator (see connectors/base.py).

    return ConnectorRegistry(connectors)
