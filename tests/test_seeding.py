"""Tests for MVP 2 startup seeding idempotency."""

from __future__ import annotations

from app.mvp2.identity.actors import (
    _ACTOR_REGISTRY,
    list_actors,
    seed_demo_actors,
)
from app.mvp2.core.policy_engine import (
    _POLICY_STORE,
    list_policies,
    seed_demo_policies,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_stores() -> None:
    """Reset both in-memory stores so each test starts fresh."""
    _ACTOR_REGISTRY.clear()
    _POLICY_STORE.clear()


# ---------------------------------------------------------------------------
# seed_demo_actors
# ---------------------------------------------------------------------------


class TestSeedDemoActors:
    def setup_method(self) -> None:
        _clear_stores()

    def teardown_method(self) -> None:
        _clear_stores()

    def test_seeds_actors_into_empty_registry(self) -> None:
        seed_demo_actors()
        actors = list_actors()
        assert len(actors) == 2
        ids = {a.actor_id for a in actors}
        assert ids == {"actor-1", "human-1"}

    def test_idempotent_no_duplicates(self) -> None:
        seed_demo_actors()
        seed_demo_actors()
        seed_demo_actors()
        assert len(list_actors()) == 2

    def test_does_not_overwrite_existing_data(self) -> None:
        """If the registry already has entries the seed is a no-op."""
        from app.mvp2.schemas.actor import ActorIdentity, ActorType

        custom = ActorIdentity(
            actor_id="custom-1",
            actor_type=ActorType.HUMAN,
            name="Custom",
            wallet_address="w",
            did="did:test:custom",
        )
        _ACTOR_REGISTRY[custom.actor_id] = custom

        seed_demo_actors()

        # The custom entry should remain; demo entries should NOT be added.
        assert len(list_actors()) == 1
        assert list_actors()[0].actor_id == "custom-1"


# ---------------------------------------------------------------------------
# seed_demo_policies
# ---------------------------------------------------------------------------


class TestSeedDemoPolicies:
    def setup_method(self) -> None:
        _clear_stores()

    def teardown_method(self) -> None:
        _clear_stores()

    def test_seeds_policies_into_empty_store(self) -> None:
        seed_demo_policies()
        policies = list_policies()
        assert len(policies) == 1
        assert policies[0].policy_id == "policy-1"

    def test_idempotent_no_duplicates(self) -> None:
        seed_demo_policies()
        seed_demo_policies()
        seed_demo_policies()
        assert len(list_policies()) == 1

    def test_does_not_overwrite_existing_data(self) -> None:
        """If the store already has entries the seed is a no-op."""
        from app.mvp2.schemas.policy import PolicyDefinition

        custom = PolicyDefinition(
            policy_id="custom-pol",
            policy_name="Custom Policy",
            policy_version="1.0",
            actor_id="custom-actor",
            max_amount=999,
            escalation_threshold=500,
            allowed_vendors=["v"],
            allowed_chains=["c"],
            allowed_assets=["a"],
        )
        _POLICY_STORE[custom.actor_id] = custom

        seed_demo_policies()

        # The custom entry should remain; demo entries should NOT be added.
        assert len(list_policies()) == 1
        assert list_policies()[0].policy_id == "custom-pol"
