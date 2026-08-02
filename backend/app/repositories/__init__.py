"""Persistence repositories for canonical domain objects.

Repositories are the *only* place canonical resources are read or written, and
**every** query is scoped by ``organization_id`` so tenant isolation cannot be
bypassed by callers.
"""
