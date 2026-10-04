from __future__ import annotations

from typing import Any


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}


class InvalidTimeRange(DomainError):
    status_code = 422
    code = "invalid_time_range"


class BehaviorOverlapError(DomainError):
    status_code = 409
    code = "behavior_overlap"


class ResourceNotFound(DomainError):
    status_code = 404
    code = "not_found"


class ResourceConflict(DomainError):
    status_code = 409
    code = "conflict"


class AuthenticationError(DomainError):
    status_code = 401
    code = "unauthenticated"