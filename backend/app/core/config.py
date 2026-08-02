"""Application settings loaded from environment variables."""

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
