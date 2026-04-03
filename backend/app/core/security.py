"""Lightweight security helpers (API-key placeholder, hashing)."""

from app.core.config import settings


def verify_api_key(api_key: str) -> bool:
    """Placeholder API-key check — replace with real auth in production."""
    return api_key == settings.SECRET_KEY
