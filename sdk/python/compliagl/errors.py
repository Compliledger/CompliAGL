from __future__ import annotations


class CompliAGLApiError(Exception):
    def __init__(self, status: int | None, code: str | None, message: str, body=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.body = body


class NotFoundError(CompliAGLApiError):
    pass


class ValidationError(CompliAGLApiError):
    pass


class ConflictError(CompliAGLApiError):
    pass


class RateLimitError(CompliAGLApiError):
    pass


class AuthError(CompliAGLApiError):
    pass


class ServerError(CompliAGLApiError):
    pass


class WebhookVerificationError(Exception):
    pass
