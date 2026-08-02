from __future__ import annotations
from .base import CrudClient


class OperationalContextClient(CrudClient):
    path = "operational-contexts"
