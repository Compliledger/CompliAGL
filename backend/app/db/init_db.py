"""Database initialisation — create all tables."""

from app.core.database import Base, engine

# Import every model so SQLAlchemy registers them on Base.metadata
from app.models.agent import Agent  # noqa: F401
from app.models.policy import Policy  # noqa: F401
from app.models.transaction import Transaction  # noqa: F401
from app.models.approval import Approval  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.proof_bundle import ProofBundle  # noqa: F401


def init_db() -> None:
    """Create database tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)
