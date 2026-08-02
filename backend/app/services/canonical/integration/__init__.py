"""Integration event system for the ProofSync, AuditSync and RegSync portals.

CompliAGL / CompliLedger remains the canonical proof source. This package
implements the outbound integration contracts and event feeds as a single,
canonical transactional-outbox event system — not three duplicate proof stores:

* :mod:`.contracts` — channel responsibilities, role scoping and the
  :class:`~.contracts.EventContract` producers emit.
* :mod:`.projections` — authorized, redacted per-channel projections (raw
  sensitive evidence is never sent by default; references are sent instead).
* :mod:`.event_signing` — deterministic signing/verification of outbound events.
* :mod:`.channel_adapter` — the outbound adapter interface + safe in-memory
  ProofSync / AuditSync / RegSync adapters.
* :mod:`.event_publisher` — the transactional-outbox publisher (reliable,
  idempotent, signed, scoped).
* :mod:`.dispatcher` — reliable delivery with retry and dead-letter status.
* :mod:`.consumer` — idempotent-consumer support.
* :mod:`.scoping` — organization + role scope enforcement.
"""
