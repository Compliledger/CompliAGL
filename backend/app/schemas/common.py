"""Common schema helpers."""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic message envelope."""

    message: str


class PaginationParams(BaseModel):
    skip: int = 0
    limit: int = 100
