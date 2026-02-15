"""
Custom logging formatters.

Provides JSON and text formatters for structured logging.

Example:
    ```python
    import logging
    from forge_shared.logging.formatter import JSONFormatter

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    ```
"""

import json
import logging
import time
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Formats log records as JSON objects with consistent schema.

    Attributes:
        timestamp_format: Timestamp format (unix or iso)

    Example:
        ```python
        handler.setFormatter(JSONFormatter())
        ```
    """

    def __init__(self, timestamp_format: str = "unix") -> None:
        """
        Initialize JSON formatter.

        Args:
            timestamp_format: Timestamp format (unix or iso)
        """
        super().__init__()
        self.timestamp_format = timestamp_format

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string
        """
        # Create base log data
        log_data: dict[str, Any] = {
            "timestamp": self._get_timestamp(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add stack trace if present
        if record.stack_info:
            log_data["stack_trace"] = self.formatStack(record.stack_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            }:
                log_data[key] = value

        return json.dumps(log_data)

    def _get_timestamp(self) -> float | str:
        """
        Get current timestamp.

        Returns:
            Timestamp in configured format
        """
        if self.timestamp_format == "iso":
            return time.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        return time.time()


class TextFormatter(logging.Formatter):
    """
    Text formatter for human-readable logging.

    Formats log records as readable text with colors for console output.

    Attributes:
        use_colors: Whether to use ANSI colors
        include_timestamp: Whether to include timestamp

    Example:
        ```python
        handler.setFormatter(TextFormatter(use_colors=True))
        ```
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def __init__(
        self,
        use_colors: bool = True,
        include_timestamp: bool = True,
    ) -> None:
        """
        Initialize text formatter.

        Args:
            use_colors: Use ANSI colors
            include_timestamp: Include timestamp in output
        """
        super().__init__()
        self.use_colors = use_colors
        self.include_timestamp = include_timestamp

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as text.

        Args:
            record: Log record to format

        Returns:
            Formatted text string
        """
        # Get level name with color
        level_name = record.levelname
        if self.use_colors:
            color = self.COLORS.get(level_name, "")
            reset = self.COLORS["RESET"]
            level_name = f"{color}{level_name}{reset}"

        # Build format parts
        parts = []

        if self.include_timestamp:
            parts.append(self.formatTime(record, "%Y-%m-%d %H:%M:%S"))

        parts.append(f"[{level_name}]")
        parts.append(f"{record.name}:{record.funcName}:{record.lineno}")
        parts.append(f"- {record.getMessage()}")

        return " ".join(parts)
