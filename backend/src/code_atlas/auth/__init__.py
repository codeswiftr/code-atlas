"""Authentication module for Code Atlas API.

Provides API key management, validation, and scope-based access control.
"""

from .api_keys import (
    APIKeyManager,
    get_key_manager,
    reset_key_manager,
)

__all__ = [
    "APIKeyManager",
    "get_key_manager",
    "reset_key_manager",
]
