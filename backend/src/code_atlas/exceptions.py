"""Custom exceptions for Code Atlas pipeline."""

from __future__ import annotations


class SessionProcessingError(Exception):
    """Raised when session processing fails."""

    pass


class CostLimitExceeded(Exception):
    """Raised when cost limits are exceeded during extraction."""

    def __init__(
        self,
        message: str,
        current_cost: float,
        limit: float,
        limit_type: str = "session",
    ) -> None:
        super().__init__(message)
        self.current_cost = current_cost
        self.limit = limit
        self.limit_type = limit_type
