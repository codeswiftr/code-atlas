"""Custom exceptions for Code Atlas pipeline."""

from __future__ import annotations


class CodeAtlasError(Exception):
    """Base exception for all Code Atlas errors."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        context: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}


class ConfigurationError(CodeAtlasError):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        config_file: str | None = None,
    ) -> None:
        context = {}
        if config_key:
            context["config_key"] = config_key
        if config_file:
            context["config_file"] = config_file
        super().__init__(message, error_code="CONFIG_ERROR", context=context)


class DiscoveryError(CodeAtlasError):
    """Raised when session discovery fails."""

    def __init__(
        self,
        message: str,
        root_path: str | None = None,
        project_name: str | None = None,
    ) -> None:
        context = {}
        if root_path:
            context["root_path"] = root_path
        if project_name:
            context["project_name"] = project_name
        super().__init__(message, error_code="DISCOVERY_ERROR", context=context)


class SessionParsingError(CodeAtlasError):
    """Raised when session parsing fails."""

    def __init__(
        self,
        message: str,
        session_id: str | None = None,
        file_path: str | None = None,
        line_number: int | None = None,
    ) -> None:
        context = {}
        if session_id:
            context["session_id"] = session_id
        if file_path:
            context["file_path"] = file_path
        if line_number:
            context["line_number"] = str(line_number)
        super().__init__(message, error_code="PARSING_ERROR", context=context)


class ExtractionError(CodeAtlasError):
    """Raised when insight extraction fails."""

    def __init__(
        self,
        message: str,
        session_id: str | None = None,
        extraction_method: str | None = None,
        model_name: str | None = None,
    ) -> None:
        context = {}
        if session_id:
            context["session_id"] = session_id
        if extraction_method:
            context["extraction_method"] = extraction_method
        if model_name:
            context["model_name"] = model_name
        super().__init__(message, error_code="EXTRACTION_ERROR", context=context)


class CostLimitExceeded(CodeAtlasError):
    """Raised when cost limits are exceeded during extraction."""

    def __init__(
        self,
        message: str,
        current_cost: float,
        limit: float,
        limit_type: str = "session",
        session_id: str | None = None,
        **kwargs,
    ) -> None:
        # Build context with cost limit information
        context = {
            "current_cost": str(current_cost),
            "limit": str(limit),
            "limit_type": limit_type,
            "extraction_method": "cost_guard",
        }
        if session_id:
            context["session_id"] = session_id

        # Call parent with context
        super().__init__(message, error_code="COST_LIMIT_EXCEEDED", context=context, **kwargs)

        # Set cost-specific attributes for backward compatibility
        self.current_cost = current_cost
        self.limit = limit
        self.limit_type = limit_type


class DatabaseError(CodeAtlasError):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        graph_name: str | None = None,
        query: str | None = None,
    ) -> None:
        context = {}
        if operation:
            context["operation"] = operation
        if graph_name:
            context["graph_name"] = graph_name
        if query:
            context["query"] = query[:200]  # Truncate long queries
        super().__init__(message, error_code="DATABASE_ERROR", context=context)


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(
        self,
        message: str,
        connection_url: str | None = None,
        retry_count: int | None = None,
    ) -> None:
        context = {}
        if connection_url:
            # Mask sensitive parts of URL
            masked_url = connection_url.split("@")[-1] if "@" in connection_url else connection_url
            context["connection_url"] = masked_url
        if retry_count:
            context["retry_count"] = str(retry_count)
        super().__init__(message, error_code="CONNECTION_ERROR", context=context)


class ValidationError(CodeAtlasError):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        field_value: str | None = None,
        schema_name: str | None = None,
    ) -> None:
        context = {}
        if field_name:
            context["field_name"] = field_name
        if field_value:
            context["field_value"] = field_value[:100]  # Truncate long values
        if schema_name:
            context["schema_name"] = schema_name
        super().__init__(message, error_code="VALIDATION_ERROR", context=context)


class ResourceExhaustedError(CodeAtlasError):
    """Raised when system resources are exhausted."""

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        current_usage: str | None = None,
        limit: str | None = None,
    ) -> None:
        context = {}
        if resource_type:
            context["resource_type"] = resource_type
        if current_usage:
            context["current_usage"] = current_usage
        if limit:
            context["limit"] = limit
        super().__init__(message, error_code="RESOURCE_EXHAUSTED", context=context)


class SessionProcessingError(CodeAtlasError):
    """Raised when session processing fails (legacy compatibility)."""

    def __init__(
        self,
        message: str,
        session_id: str | None = None,
        stage: str | None = None,
    ) -> None:
        context = {}
        if session_id:
            context["session_id"] = session_id
        if stage:
            context["stage"] = stage
        super().__init__(message, error_code="SESSION_PROCESSING_ERROR", context=context)


class RetryableError(CodeAtlasError):
    """Base class for errors that can be retried."""

    def __init__(
        self,
        message: str,
        retry_count: int = 0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        **kwargs,
    ) -> None:
        super().__init__(message, error_code="RETRYABLE_ERROR", **kwargs)
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds


class NonRetryableError(CodeAtlasError):
    """Base class for errors that should not be retried."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(message, error_code="NON_RETRYABLE_ERROR", **kwargs)
