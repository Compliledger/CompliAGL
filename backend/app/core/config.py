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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
