"""Audit log Pydantic schemas."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, model_validator


class AuditLogResponse(BaseModel):
    id: str
    agent_id: str
    transaction_id: Optional[str] = None
    event_type: str
    event_summary: str
    event_data: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _parse_event_data(cls, data: Any) -> Any:
        """Deserialise the JSON text stored in event_data."""
        if hasattr(data, "__dict__"):
            raw = getattr(data, "event_data", None)
        else:
            raw = data.get("event_data") if isinstance(data, dict) else None
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if hasattr(data, "__dict__"):
                object.__setattr__(data, "event_data", parsed)
            else:
                data["event_data"] = parsed
        return data


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
