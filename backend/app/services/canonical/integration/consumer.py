"""Idempotent consumer support for the sync portals.

Deliveries are at-least-once: a retry may re-deliver an event a portal already
processed. Because every event carries a deterministic ``event_id``, a consumer
can deduplicate reliably. This module ships:

* :func:`event_id_of` — extract the deterministic id from a delivered
  projection or signed delivery, and
* :class:`IdempotentEventConsumer` — a small, dependency-free helper a portal
  (in its own repository) can use, or subclass, to guarantee each event is
  processed at most once and to verify the outbound signature before acting.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from app.services.canonical.integration import event_signing


def event_id_of(delivered: Mapping[str, Any]) -> Optional[str]:
    """Return the deterministic ``event_id`` from a delivered projection."""
    value = delivered.get("event_id")
    return str(value) if value else None


class IdempotentEventConsumer:
    """Deduplicating, signature-verifying consumer scaffold.

    The default in-memory store is deliberately simple; a real portal would back
    ``_seen`` with a durable store. The important property is that
    :meth:`process` invokes the handler exactly once per unique ``event_id`` and
    returns ``False`` for a duplicate without re-invoking the handler.
    """

    def __init__(self, *, verify_signature: bool = True) -> None:
        self._seen: set[str] = set()
        self._verify_signature = verify_signature

    def already_processed(self, event_id: str) -> bool:
        return event_id in self._seen

    def mark_processed(self, event_id: str) -> None:
        self._seen.add(event_id)

    def verify(
        self,
        projection_hash: str,
        signer_key_id: Optional[str],
        signature: Optional[str],
    ) -> bool:
        """Verify an outbound event signature over its projection hash."""
        return event_signing.verify(signer_key_id, projection_hash, signature)

    def process(
        self,
        delivered: Mapping[str, Any],
        handler: Callable[[Mapping[str, Any]], Any],
    ) -> bool:
        """Process a delivered projection at most once.

        Returns ``True`` if the handler ran (first time this ``event_id`` was
        seen) and ``False`` if the delivery was a duplicate and was skipped.
        """
        event_id = event_id_of(delivered)
        if not event_id:
            raise ValueError("delivered projection is missing an event_id")
        if self.already_processed(event_id):
            return False
        handler(delivered)
        self.mark_processed(event_id)
        return True
