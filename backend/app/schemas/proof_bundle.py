"""ProofBundle Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ProofBundleResponse(BaseModel):
    id: str
    transaction_id: str
    decision: str
    policy_snapshot: list[dict[str, Any]] | str
    evaluation_results: list[dict[str, Any]] | str
    proof_hash: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
