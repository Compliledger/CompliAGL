from __future__ import annotations

from .clients import (
    AIProofClient,
    ActorIdentityClient,
    AuthorizationClient,
    DecisionClient,
    EvaluationClient,
    EvidenceClient,
    ExecutionResultClient,
    IntentClient,
    OperationalContextClient,
    TargetClient,
    VerificationClient,
)
from .config import CompliAGLConfig
from .http import HttpClient


class CompliAGL:
    def __init__(self, config: CompliAGLConfig | None = None, **kwargs):
        self.config = config or CompliAGLConfig(**kwargs)
        self.http = HttpClient(self.config)
        self.actor_identities = ActorIdentityClient(self.http)
        self.intents = IntentClient(self.http)
        self.targets = TargetClient(self.http)
        self.operational_contexts = OperationalContextClient(self.http)
        self.evaluations = EvaluationClient(self.http)
        self.evidence = EvidenceClient(self.http)
        self.decisions = DecisionClient(self.http)
        self.authorizations = AuthorizationClient(self.http)
        self.execution_results = ExecutionResultClient(self.http)
        self.aiproofs = AIProofClient(self.http)
        self.verification = VerificationClient(self.http)
        self.actorIdentities = self.actor_identities
        self.operationalContexts = self.operational_contexts
        self.executionResults = self.execution_results
