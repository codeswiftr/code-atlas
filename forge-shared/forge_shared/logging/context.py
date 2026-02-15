"""
Logging context for request-scoped data.

Provides context management for adding request-specific data to logs.

Example:
    ```python
    from forge_shared.logging.context import LoggingContext

    with LoggingContext(request_id="123", user_id="456"):
        logger.info("Processing request")
    ```
"""

import contextvars
from typing import Any, Optional

# Context variables for logging
_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)
_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_id", default=None
)
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)
_custom_fields: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "custom_fields", default={}
)


class LoggingContext:
    """
    Context manager for logging context.

    Manages request-scoped logging data like request ID, user ID, and
    correlation ID.

    Example:
        ```python
        with LoggingContext(request_id="123", user_id="456"):
            logger.info("Processing request")
        ```
    """

    def __init__(
        self,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize logging context.

        Args:
            request_id: Request ID
            user_id: User ID
            correlation_id: Correlation ID
            **kwargs: Additional custom fields
        """
        self.request_id = request_id
        self.user_id = user_id
        self.correlation_id = correlation_id
        self.custom_fields = kwargs
        self._tokens: list[contextvars.Token] = []

    def __enter__(self) -> "LoggingContext":
        """Enter context and set context variables."""
        if self.request_id:
            self._tokens.append(_request_id.set(self.request_id))
        if self.user_id:
            self._tokens.append(_user_id.set(self.user_id))
        if self.correlation_id:
            self._tokens.append(_correlation_id.set(self.correlation_id))
        if self.custom_fields:
            self._tokens.append(_custom_fields.set(self.custom_fields))
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context and reset context variables."""
        for token in self._tokens:
            _custom_fields.reset(token)


def get_logging_context() -> dict[str, Any]:
    """
    Get current logging context as dictionary.

    Returns:
        Dictionary with current context values

    Example:
        ```python
        context = get_logging_context()
        logger.info("Processing", extra=context)
        ```
    """
    context = {}

    request_id = _request_id.get()
    if request_id:
        context["request_id"] = request_id

    user_id = _user_id.get()
    if user_id:
        context["user_id"] = user_id

    correlation_id = _correlation_id.get()
    if correlation_id:
        context["correlation_id"] = correlation_id

    custom_fields = _custom_fields.get()
    if custom_fields:
        context.update(custom_fields)

    return context


def set_request_id(request_id: str) -> None:
    """
    Set request ID in logging context.

    Args:
        request_id: Request ID to set
    """
    _request_id.set(request_id)


def set_user_id(user_id: str) -> None:
    """
    Set user ID in logging context.

    Args:
        user_id: User ID to set
    """
    _user_id.set(user_id)


def set_correlation_id(correlation_id: str) -> None:
    """
    Set correlation ID in logging context.

    Args:
        correlation_id: Correlation ID to set
    """
    _correlation_id.set(correlation_id)


def add_custom_field(key: str, value: Any) -> None:
    """
    Add custom field to logging context.

    Args:
        key: Field name
        value: Field value
    """
    fields = _custom_fields.get()
    fields[key] = value
    _custom_fields.set(fields)
