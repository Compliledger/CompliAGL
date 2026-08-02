from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AgentIdentityProvider(Protocol):
    def get_actor_identity(self) -> dict[str, Any]: ...

    def getActorIdentity(self) -> dict[str, Any]: ...


@runtime_checkable
class EvidenceProvider(Protocol):
    def collect_evidence(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...

    def collectEvidence(self, request: dict[str, Any]) -> list[dict[str, Any]]: ...


@runtime_checkable
class ExternalExecutionSystem(Protocol):
    def execute(self, authorization: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class MerchantSystem(ExternalExecutionSystem, Protocol):
    def select_offer(self, params: dict[str, Any]) -> dict[str, Any]: ...

    def selectOffer(self, params: dict[str, Any]) -> dict[str, Any]: ...

    def fulfill(self, authorization: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class PaymentSystem(ExternalExecutionSystem, Protocol):
    def settle(self, authorization: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class HederaAgentAccount(Protocol):
    account_id: str

    def sign(self, payload: bytes) -> bytes: ...


@runtime_checkable
class ProofVerifier(Protocol):
    def verify(self, proof: dict[str, Any]) -> bool: ...
