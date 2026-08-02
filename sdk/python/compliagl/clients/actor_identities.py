from __future__ import annotations
from .base import CrudClient


class ActorIdentityClient(CrudClient):
    path = "actor-identities"
