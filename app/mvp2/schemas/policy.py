"""Policy schemas for CompliAGL MVP 2."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PolicyRule(BaseModel):
    """A single rule within a policy definition."""

    rule_id: str
    field: str
    operator: str
    value: str | int | float | bool


class PolicyDefinition(BaseModel):
    """Full policy definition governing actor transactions."""

    policy_id: str
    policy_name: str
    policy_version: str
    actor_id: str
    max_amount: float
    escalation_threshold: float
    allowed_vendors: list[str] = Field(default_factory=list)
    allowed_chains: list[str] = Field(default_factory=list)
    allowed_assets: list[str] = Field(default_factory=list)
    rules: list[PolicyRule] = Field(default_factory=list)
