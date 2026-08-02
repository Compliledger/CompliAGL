from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping

from .enums import ExecutionResultStatus


def _clean(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {k: _clean(v) for k, v in asdict(value).items() if v is not None}
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


class ModelMixin:
    def to_dict(self) -> dict[str, Any]:
        return _clean(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in dict(data).items() if k in names})


@dataclass
class ActorIdentity(ModelMixin):
    id: str | None = None
    actor_type: str | None = None
    credential_type: str | None = None
    external_id: str | None = None
    display_name: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class Intent(ModelMixin):
    id: str | None = None
    actor_identity_id: str | None = None
    intent_type: str | None = None
    status: str | None = None
    description: str | None = None
    amount_minor: int | None = None
    amount_currency: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class Target(ModelMixin):
    id: str | None = None
    target_type: str | None = None
    name: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class OperationalContext(ModelMixin):
    id: str | None = None
    environment: str | None = None
    target_id: str | None = None
    intent_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class GovernanceEvaluation(ModelMixin):
    id: str | None = None
    intent_id: str | None = None
    target_id: str | None = None
    operational_context_id: str | None = None
    status: str | None = None
    outcome: str | None = None
    reason_codes: list[str] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class EvidenceCollection(ModelMixin):
    id: str | None = None
    job_id: str | None = None
    requirement: str | None = None
    status: str | None = None
    items: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class Decision(ModelMixin):
    id: str | None = None
    policy_resolution_id: str | None = None
    outcome: str | None = None
    reason_codes: list[str] | None = None
    prior_decision_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class ExecutionAuthorization(ModelMixin):
    id: str | None = None
    decision_id: str | None = None
    status: str | None = None
    max_amount_minor: int | None = None
    amount_currency: str | None = None
    expires_at: str | None = None
    signature: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class ExternalExecutionResult(ModelMixin):
    execution_result_id: str
    authorization_id: str
    external_system_id: str
    status: ExecutionResultStatus | str
    executed_action: str
    target: str | dict[str, Any]
    result_payload_hash: str
    executed_at: str
    submitted_at: str
    signer_key_id: str
    signature: str
    provenance: dict[str, Any]
    amount_minor: int | None = None
    amount_currency: str | None = None
    external_reference: str | None = None
    payment_or_settlement_reference: str | None = None
    metadata: dict[str, Any] | None = None
    result_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["execution_authorization_id"] = data.pop("authorization_id")
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]):
        raw = dict(data)
        if "execution_authorization_id" in raw and "authorization_id" not in raw:
            raw["authorization_id"] = raw.pop("execution_authorization_id")
        return super().from_dict(raw)


@dataclass
class AIProof(ModelMixin):
    id: str | None = None
    execution_result_id: str | None = None
    proof_hash: str | None = None
    signature: str | None = None
    verified: bool | None = None
    metadata: dict[str, Any] | None = None
