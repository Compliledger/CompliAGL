# CompliAGL — Anchoring Integration (`mvp2/anchor`)

This package is a **thin integration wrapper** over the shared
[`compliledger-algorand-adapter`](https://github.com/Compliledger) repository.

CompliAGL is chain-agnostic and **does not reimplement** Algorand anchoring
logic. The Algorand client, hashing, transaction builder, and on-chain
registry all live in the shared adapter and are *reused* here. This wrapper
only maps a CompliAGL **AIProof** bundle onto the adapter's canonical
`ProofSchema` and delegates anchoring/verification to the adapter's services.

## Installing the shared adapter locally

The shared adapter is an **optional dependency** and is imported lazily, so
CompliAGL stays importable and testable even when the adapter is not present.
To enable anchoring locally, install the adapter.

**Preferred (local / development): editable install**

Clone the adapter next to this repository and install it in editable mode so
local changes are picked up immediately:

```bash
# from the CompliAGL/backend directory, with your virtualenv active
git clone https://github.com/Compliledger/compliledger-algorand-adapter ../compliledger-algorand-adapter
pip install -e ../compliledger-algorand-adapter
```

You can also record the editable dependency in a requirements file:

```text
# requirements-adapter.txt
-e ../compliledger-algorand-adapter
```

```bash
pip install -r requirements-adapter.txt
```

> The editable path is intentionally **not** added to `requirements.txt`
> because the adapter lives in a separate repository whose checkout location
> varies per environment. Keeping it out of the core requirements lets the
> backend install and run without the adapter present.

## Usage

```python
from app.mvp2.anchor.algorand_adapter_service import (
    anchor_ai_proof_bundle,
    build_proof_schema_from_aiproof,
    verify_anchored_proof,
)

# Map a CompliAGL AIProof bundle onto the shared adapter ProofSchema.
schema = build_proof_schema_from_aiproof(ai_proof_bundle)

# Anchor it on-chain via the shared adapter and get a receipt back.
receipt = anchor_ai_proof_bundle(ai_proof_bundle)

# Later, independently verify the anchored proof.
state = verify_anchored_proof(asset_id=receipt["proof_hash"])
```

## AIProof → `ProofSchema` mapping

| `ProofSchema` field   | CompliAGL AIProof source                                   |
|-----------------------|-------------------------------------------------------------|
| `module_name`         | constant `"CompliAGL"`                                       |
| `asset_id`            | `actor_id` or `intent_id`                                   |
| `state_type`          | constant `"autonomous_execution"`                           |
| `decision_status`     | `decision`                                                  |
| `policy_version`      | `policy_version`                                            |
| `proof_snapshot_hash` | `proof_hash`                                                |
| `timestamp`           | `created_at`                                                |
| `reason_codes`        | `decision_reason` or `reason_codes`                         |
| `metadata`            | actor, intent, execution adapter, payment reference, x402   |

## Anchor receipt

`anchor_ai_proof_bundle()` returns a receipt with the following keys:

| Field             | Description                                       |
|-------------------|---------------------------------------------------|
| `chain`           | `"algorand"`                                      |
| `network`         | Network the proof was anchored on                 |
| `proof_hash`      | Anchored proof snapshot hash                       |
| `txid`            | Anchoring transaction id                           |
| `explorer_url`    | Block explorer URL for the transaction             |
| `anchored_at`     | Timestamp the proof was anchored                   |
| `adapter`         | `"compliledger-algorand-adapter"`                  |
| `adapter_version` | Installed version of the shared adapter            |
