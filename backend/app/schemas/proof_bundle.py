"""ProofBundle Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ProofBundleResponse(BaseModel):
    id: str
    transaction_id: str
    agent_id: str
    module: str
    entity_id: str
    rule_version_used: str
    decision_result: str
    evaluation_context: Any
    reason_codes: Any
    timestamp: Optional[datetime] = None
    bundle_hash: str
    proof_status: str
    anchor_metadata: Optional[Any] = None

    model_config = {"from_attributes": True}
