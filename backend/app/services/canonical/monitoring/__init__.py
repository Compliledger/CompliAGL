"""Continuous monitoring & automated re-evaluation.

This package implements the continuous-monitoring branch of the canonical
CompliAGL lifecycle:

* :mod:`change_detector` — the :class:`ChangeDetector` interface plus a default
  state-hash detector and the registry of monitored change categories.
* :mod:`monitoring_service` — records :class:`MonitoringEvent` change events and
  publishes ``monitoring.change_detected`` to the sync portals.
* :mod:`impact_analysis` — determines which intents, evaluations, decisions,
  authorizations, findings, AIProofs and canonical proof packages a change
  affects.
* :mod:`supersession_service` — decision supersession (immutable prior decision,
  new current decision) + decision-chain retrieval.
* :mod:`authorization_invalidation` — revoke / invalidate authorizations whose
  supporting conditions no longer hold.
* :mod:`proof_supersession` — build a new AIProof that supersedes the prior proof
  (never deletes it) + proof-chain retrieval.
* :mod:`reevaluation_job` — orchestrates a full automated re-evaluation run.
"""

from __future__ import annotations
