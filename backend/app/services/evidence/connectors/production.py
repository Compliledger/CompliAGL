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
from app.services.evidence.connectors.harborstone_screening_placeholder import (
    HARBORSTONE_SCREENING_PLACEHOLDER_ACK,
    harborstone_screening_placeholder_connector,
)
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

    # PLACEHOLDER -- not a real evidence source. Registers a hardcoded stand-in
    # connector for the HarborStone package's placeholder sanctions-screening
    # requirement (REQ/CTL/EV-PLACEHOLDER-SANCTIONS-SCREENING, the control
    # itself being evaluation_expression "True") so the decision-engine +
    # CompliIdentity authority-context chain can be exercised end to end over
    # HTTP -- the analog of demo3_step2/compliagl_scenarios.py's in-process
    # mock. Gated on an explicit acknowledgement string, not a truthy flag. A
    # real deployment NEVER sets this: the evidence type then has no connector
    # and the mandatory control fails closed, exactly as it does today. Delete
    # this together with the placeholder package content and the connector.
    # See PENDING_REVIEW_harborstone_screening_control_placeholder.md.
    if (
        os.environ.get("COMPLIAGL_HARBORSTONE_SCREENING_PLACEHOLDER")
        == HARBORSTONE_SCREENING_PLACEHOLDER_ACK
    ):
        connectors.append(harborstone_screening_placeholder_connector())

    return ConnectorRegistry(connectors)
