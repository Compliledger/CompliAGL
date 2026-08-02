"""Supersession service — immutable decision chains.

Decisions are immutable. A re-evaluation never mutates an existing decision; it
creates a **new** :class:`Decision` and marks the prior current decision as
``SUPERSEDED``, linking the two both ways (``prior_decision_id`` on the new
decision, ``superseded_by_decision_id`` on the old). This keeps the full,
ordered decision history available and verifiable.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.repositories.canonical import DecisionRepository
from app.utils.canonical_enums import DecisionSupersessionStatus


def supersede_decision(
    db: Session, prior_decision: Optional[Decision], new_decision: Decision
) -> None:
    """Mark ``prior_decision`` superseded by ``new_decision`` (immutable link)."""
    if prior_decision is None or prior_decision.id == new_decision.id:
        return
    prior_decision.supersession_status = (
        DecisionSupersessionStatus.SUPERSEDED.value
    )
    prior_decision.superseded_by_decision_id = new_decision.id
    DecisionRepository(db).save(prior_decision)


def _entry(decision: Decision) -> dict[str, Any]:
    return {
        "decision_id": decision.id,
        "outcome": decision.outcome,
        "supersession_status": decision.supersession_status,
        "prior_decision_id": decision.prior_decision_id,
        "superseded_by_decision_id": decision.superseded_by_decision_id,
        "originating_finding_id": getattr(
            decision, "originating_finding_id", None
        ),
        "decision_hash": decision.decision_hash,
        "decided_at": decision.decided_at,
        "reason_codes": json.loads(decision.reason_codes or "[]"),
    }


def decision_chain(
    db: Session, organization_id: str, decision_id: str
) -> Optional[dict[str, Any]]:
    """Return the full supersession chain a decision belongs to.

    The chain is walked back to the root (via ``prior_decision_id``) and forward
    to the current decision (via ``superseded_by_decision_id``), so any decision
    id in the chain returns the same ordered history.
    """
    repo = DecisionRepository(db)
    anchor = repo.get(organization_id, decision_id)
    if anchor is None:
        return None

    # Walk back to the root.
    root = anchor
    seen: set[str] = {root.id}
    while root.prior_decision_id:
        prior = repo.get(organization_id, root.prior_decision_id)
        if prior is None or prior.id in seen:
            break
        seen.add(prior.id)
        root = prior

    # Walk forward from the root building the ordered chain.
    chain: list[Decision] = [root]
    walked: set[str] = {root.id}
    current = root
    while current.superseded_by_decision_id:
        nxt = repo.get(organization_id, current.superseded_by_decision_id)
        if nxt is None or nxt.id in walked:
            break
        walked.add(nxt.id)
        chain.append(nxt)
        current = nxt

    current_id = chain[-1].id if chain else anchor.id
    return {
        "anchor_decision_id": decision_id,
        "root_decision_id": root.id,
        "current_decision_id": current_id,
        "length": len(chain),
        "chain": [_entry(d) for d in chain],
    }
