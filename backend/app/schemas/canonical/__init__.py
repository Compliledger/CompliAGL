"""Pydantic request/response schemas for canonical domain objects.

API request schemas (``*Create`` / ``*Update``) are kept separate from the
persistent ORM models and from the ``*Response`` read schemas so the wire
contract can evolve independently of storage.
"""
