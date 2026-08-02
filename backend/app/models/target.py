"""Target ORM model — canonical first-class resource.

A **Target** is the thing an intent acts upon. It is no longer inferred only
from a vendor or destination field: it is an explicit, typed, first-class
resource drawn from the universal target taxonomy (ACTOR, ASSET, TRANSACTION,
SYSTEM, MODEL, DEVICE, PROCESS, DATASET, MERCHANT, API, SMART_CONTRACT, ACCOUNT,
WORKFLOW, CUSTOM).
"""

from __future__ import annotations

from sqlalchemy import Column, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import TargetType, TrustStatus


class Target(CanonicalMixin, Base):
    """Persistent, typed target of an intent."""

    __tablename__ = "targets"

    target_type = Column(String, nullable=False)
    external_identifier = Column(String, nullable=True, index=True)
    owner = Column(String, nullable=True)

    # ``organization`` is the target's own owning organization label; tenant
    # isolation is provided separately by CanonicalMixin.organization_id.
    organization = Column(String, nullable=True)

    classification = Column(String, nullable=True)
    trust_status = Column(
        String, nullable=False, default=TrustStatus.UNKNOWN.value
    )
    network_or_environment = Column(String, nullable=True)

    target_metadata = Column(Text, nullable=True)
