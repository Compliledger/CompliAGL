"""Anchoring integration for MVP 2.

This package contains a *thin* integration layer over the shared
``compliledger-algorand-adapter`` repository. CompliAGL deliberately does
**not** reimplement Algorand client, hashing, transaction builder, or
registry logic — that lives in the shared adapter. The wrapper here only
maps CompliAGL's AIProof bundles onto the adapter's ``ProofSchema`` and
delegates anchoring/verification to the adapter.
"""
