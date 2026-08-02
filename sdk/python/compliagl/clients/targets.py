from __future__ import annotations
from .base import CrudClient


class TargetClient(CrudClient):
    path = "targets"
