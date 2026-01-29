"""PostHog analytics service for Code Atlas."""

from __future__ import annotations

import logging
from typing import Any

try:
    import posthog

    HAS_POSTHOG = True
except ImportError:
    HAS_POSTHOG = False

from .config import AtlasSettings

logger = logging.getLogger(__name__)


class PostHogAnalytics:
    """PostHog analytics client for Code Atlas events."""

    _initialized = False
    _settings: AtlasSettings | None = None

    @classmethod
    def initialize(cls, settings: AtlasSettings | None = None) -> None:
        """Initialize PostHog client."""
        if cls._initialized:
            return

        if not HAS_POSTHOG:
            logger.warning("PostHog package not installed - analytics disabled")
            return

        cls._settings = settings or AtlasSettings()
        api_key = cls._settings.posthog_api_key
        host = cls._settings.posthog_host

        if not api_key:
            logger.warning("PostHog API key not configured - analytics disabled")
            return

        posthog.project_api_key = api_key
        posthog.host = host
        posthog.debug = cls._settings.debug
        cls._initialized = True
        logger.info("PostHog analytics initialized")

    @classmethod
    def capture(
        cls,
        user_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Capture an analytics event."""
        if not cls._initialized:
            cls.initialize()

        if not cls._initialized or not HAS_POSTHOG:
            return

        try:
            posthog.capture(
                distinct_id=user_id,
                event=event,
                properties={
                    "product": "code-atlas",
                    **(properties or {}),
                },
            )
        except Exception as e:
            logger.error(f"PostHog capture failed: {e}")

    @classmethod
    def identify(
        cls,
        user_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Identify a user with properties."""
        if not cls._initialized:
            cls.initialize()

        if not cls._initialized or not HAS_POSTHOG:
            return

        try:
            posthog.identify(user_id, properties or {})
        except Exception as e:
            logger.error(f"PostHog identify failed: {e}")

    # Code Atlas-specific events
    @classmethod
    def codebase_uploaded(
        cls,
        user_id: str,
        project_id: str,
        file_count: int,
    ) -> None:
        """Track codebase upload."""
        cls.capture(
            user_id=user_id,
            event="ca_codebase_uploaded",
            properties={
                "project_id": project_id,
                "file_count": file_count,
            },
        )

    @classmethod
    def graph_generated(
        cls,
        user_id: str,
        project_id: str,
        entity_count: int,
        relationship_count: int,
    ) -> None:
        """Track knowledge graph generation."""
        cls.capture(
            user_id=user_id,
            event="ca_graph_generated",
            properties={
                "project_id": project_id,
                "entity_count": entity_count,
                "relationship_count": relationship_count,
            },
        )

    @classmethod
    def query_run(
        cls,
        user_id: str,
        query_type: str,
        result_count: int,
    ) -> None:
        """Track graph query execution."""
        cls.capture(
            user_id=user_id,
            event="ca_query_run",
            properties={
                "query_type": query_type,
                "result_count": result_count,
            },
        )

    @classmethod
    def session_processed(
        cls,
        user_id: str,
        session_id: str,
        entity_count: int,
    ) -> None:
        """Track Claude session processing."""
        cls.capture(
            user_id=user_id,
            event="ca_session_processed",
            properties={
                "session_id": session_id,
                "entity_count": entity_count,
            },
        )

    @classmethod
    def insight_extracted(
        cls,
        user_id: str,
        insight_type: str,
    ) -> None:
        """Track insight extraction."""
        cls.capture(
            user_id=user_id,
            event="ca_insight_extracted",
            properties={
                "insight_type": insight_type,
            },
        )
