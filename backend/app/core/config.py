"""Application settings loaded from environment variables."""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration read from env vars / .env file."""

    APP_NAME: str = "CompliAGL"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./compliagl.db"
    SECRET_KEY: str = "change-me-to-a-random-secret"

    # ── x402 payment execution adapter ───────────────────────────────
    # Facilitator endpoint used to verify payments. Leave empty (or set
    # to "mock") to use the built-in mock facilitator for local dev.
    X402_FACILITATOR_URL: str = ""
    # Wallet/address that should receive the x402 payment.
    X402_RECIPIENT_ADDRESS: str = ""
    # Price (in USDC) required to authorise an autonomous action.
    X402_PRICE_USDC: float = 0.0
    # Network the payment is expected to settle on (e.g. "base-sepolia").
    X402_NETWORK: str = "base-sepolia"
    # Force the built-in mock facilitator regardless of X402_FACILITATOR_URL.
    # Keeps the Compli402 demo self-contained (no external services/secrets).
    X402_MOCK_MODE: bool = True

    # ── Executable governance package signing ────────────────────────
    # Optional registry of signing keys used to verify the signatures on
    # published governance packages, as a mapping of ``signer_key_id`` to a
    # shared secret. When empty, signing is "not configured" and packages are
    # accepted without a signature. When populated, any package that supplies a
    # signer_key_id/signature must present a valid signature or be rejected.
    GOVERNANCE_SIGNING_KEYS: dict[str, str] = {}

    # ── Executable governance package approval authority ─────────────
    # When true, ``governance_package_service.approve()`` verifies the
    # approver's authority to approve (CompliIdentity ``governance.package`` /
    # ``approve``) and rejects the approval fail-closed if it cannot. When
    # false (default), the approver principal id + rationale are still required
    # and recorded but not verified -- mirrors ``GOVERNANCE_SIGNING_KEYS``
    # (empty means "not enforced").
    GOVERNANCE_APPROVAL_AUTHORITY_REQUIRED: bool = False

    # ── Execution authorization signing ──────────────────────────────
    # Registry of signing keys used to sign and independently verify issued
    # ExecutionAuthorizations, as a mapping of ``signer_key_id`` to a private
    # signing secret. These are **private signing keys** and MUST be supplied
    # through environment-backed secret management (environment variables / a
    # secrets manager) — never committed to source. See
    # ``app/services/canonical/authorization_signing.py`` for the documented
    # signing interface.
    #
    # Set via the ``AUTHORIZATION_SIGNING_KEYS`` environment variable, e.g.
    # ``AUTHORIZATION_SIGNING_KEYS={"auth-key-1": "..."}``. When empty, the
    # service derives a single deterministic development key from ``SECRET_KEY``
    # (also environment-backed) so authorizations are always signed and never
    # emitted unsigned.
    AUTHORIZATION_SIGNING_KEYS: dict[str, str] = {}
    # The ``signer_key_id`` used to sign newly issued authorizations. When empty
    # the first configured key (or the SECRET_KEY-derived development key) is
    # used.
    AUTHORIZATION_ACTIVE_SIGNER_KEY_ID: str = ""
    # Default authorization time-to-live (seconds) applied when an issue request
    # does not specify an explicit ``expires_at``. Narrow, replay-resistant
    # authorizations should be short-lived.
    AUTHORIZATION_DEFAULT_TTL_SECONDS: int = 900

    # ── Escalation-approval orchestration ────────────────────────────
    # Default lifetime (seconds) of a human ``EscalationApproval`` when the
    # submitter does not supply an explicit ``valid_until``. Mirrors
    # ``AUTHORIZATION_DEFAULT_TTL_SECONDS`` — a human approval of an escalated
    # decision is a narrow, replay-resistant window, not a standing grant.
    ESCALATION_APPROVAL_TTL_SECONDS: int = 900

    # ── Integration event signing (ProofSync / AuditSync / RegSync) ──────
    # Registry of signing keys used to sign and independently verify outbound
    # integration events, as a mapping of ``signer_key_id`` to a private signing
    # secret. These are **private signing keys** and MUST be supplied through
    # environment-backed secret management — never committed to source. When
    # empty, a single deterministic development key is derived from ``SECRET_KEY``
    # so every outbound event is always signed and never emitted unsigned.
    #
    # Set via the ``EVENT_SIGNING_KEYS`` environment variable, e.g.
    # ``EVENT_SIGNING_KEYS={"event-key-1": "..."}``.
    EVENT_SIGNING_KEYS: dict[str, str] = {}
    # The ``signer_key_id`` used to sign newly published events. When empty the
    # first configured key (or the SECRET_KEY-derived development key) is used.
    EVENT_ACTIVE_SIGNER_KEY_ID: str = ""
    # Maximum number of delivery attempts before a delivery is dead-lettered.
    EVENT_MAX_DELIVERY_ATTEMPTS: int = 5
    # Base back-off (seconds) applied between delivery retries.
    EVENT_RETRY_BACKOFF_SECONDS: int = 30
    # ── AIProof signing ──────────────────────────────────────────────
    # Registry of signing keys used to sign and independently verify canonical
    # AIProofs, as a mapping of ``signer_key_id`` to a private signing secret.
    # These are **private signing keys** and MUST be supplied through
    # environment-backed secret management — never committed to source. When
    # empty, the service derives a single deterministic development key from
    # ``SECRET_KEY`` so AIProofs are always signable. See
    # ``app/services/canonical/aiproof/signing.py`` for the documented interface.
    AIPROOF_SIGNING_KEYS: dict[str, str] = {}
    # The ``signer_key_id`` used to sign newly generated AIProofs. When empty the
    # first configured key (or the SECRET_KEY-derived development key) is used.
    AIPROOF_ACTIVE_SIGNER_KEY_ID: str = ""
    # Logical issuer identity stamped into every AIProof (the CompliAGL instance
    # that generated and signed it).
    AIPROOF_ISSUER: str = "CompliAGL"

    # ── Astra (AIRA / SENTRY) tool-calling layer ─────────────────────
    # ``gpt-6-astra`` via OpenAI's Responses API powers both agent personas.
    # Only the Responses API transport (``app/astra/responses/client.py``)
    # needs the key -- tool schemas and dispatch work without it. ``ASTRA_ENABLED``
    # gates the agent loop specifically (fail-closed: false = loop refuses to
    # run), independent of whether a key is present.
    OPENAI_API_KEY: Optional[str] = None
    ASTRA_MODEL: str = "gpt-6-astra"
    ASTRA_ENABLED: bool = False
    ASTRA_MAX_TOOL_ITERATIONS: int = 8

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
