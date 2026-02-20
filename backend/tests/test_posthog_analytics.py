"""Unit tests for PostHog analytics integration."""

from unittest.mock import patch

import pytest

from code_atlas.config import AtlasSettings


class TestPostHogAnalytics:
    """Tests for PostHogAnalytics class."""

    @pytest.fixture(autouse=True)
    def reset_analytics(self):
        """Reset analytics state before each test."""
        # Import here to avoid import errors if posthog not installed
        from code_atlas.posthog_analytics import PostHogAnalytics

        PostHogAnalytics._initialized = False
        PostHogAnalytics._settings = None
        yield
        PostHogAnalytics._initialized = False
        PostHogAnalytics._settings = None

    def test_initialize_with_api_key(self):
        """Test initialization with valid API key."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(
            posthog_api_key="phc_test_key_12345",
            posthog_host="https://app.posthog.com",
        )

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)

                assert PostHogAnalytics._initialized is True
                assert mock_posthog.project_api_key == "phc_test_key_12345"
                assert mock_posthog.host == "https://app.posthog.com"

    def test_initialize_without_api_key(self):
        """Test initialization without API key (analytics disabled)."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key=None)

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            PostHogAnalytics.initialize(settings)

            assert PostHogAnalytics._initialized is False

    def test_initialize_without_posthog_package(self):
        """Test initialization when PostHog package is not installed."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", False):
            PostHogAnalytics.initialize(settings)

            assert PostHogAnalytics._initialized is False

    def test_initialize_idempotent(self):
        """Test that initialize can be called multiple times safely."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog"):
                PostHogAnalytics.initialize(settings)
                first_init = PostHogAnalytics._initialized

                # Second initialization should be a no-op
                PostHogAnalytics.initialize(settings)

                assert PostHogAnalytics._initialized == first_init

    def test_capture_event(self):
        """Test capturing analytics events."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)

                PostHogAnalytics.capture(
                    user_id="user-123",
                    event="test_event",
                    properties={"key": "value"},
                )

                mock_posthog.capture.assert_called_once_with(
                    distinct_id="user-123",
                    event="test_event",
                    properties={
                        "product": "code-atlas",
                        "key": "value",
                    },
                )

    def test_capture_without_properties(self):
        """Test capturing events without additional properties."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)

                PostHogAnalytics.capture(
                    user_id="user-123",
                    event="simple_event",
                )

                mock_posthog.capture.assert_called_once_with(
                    distinct_id="user-123",
                    event="simple_event",
                    properties={"product": "code-atlas"},
                )

    def test_capture_when_not_initialized(self):
        """Test that capture auto-initializes if needed."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog"):
                # Should not raise an exception
                PostHogAnalytics.capture(
                    user_id="user-123",
                    event="test_event",
                )

    def test_capture_handles_errors(self):
        """Test that capture handles errors gracefully."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)
                mock_posthog.capture.side_effect = Exception("Network error")

                # Should not raise an exception
                PostHogAnalytics.capture(
                    user_id="user-123",
                    event="test_event",
                )

    def test_identify_user(self):
        """Test identifying users."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)

                PostHogAnalytics.identify(
                    user_id="user-123",
                    properties={"email": "user@example.com", "plan": "pro"},
                )

                mock_posthog.identify.assert_called_once_with(
                    "user-123",
                    {"email": "user@example.com", "plan": "pro"},
                )

    def test_identify_handles_errors(self):
        """Test that identify handles errors gracefully."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)
                mock_posthog.identify.side_effect = Exception("Network error")

                # Should not raise an exception
                PostHogAnalytics.identify(
                    user_id="user-123",
                    properties={"email": "user@example.com"},
                )

    def test_codebase_uploaded_event(self):
        """Test codebase uploaded event tracking."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)

                PostHogAnalytics.codebase_uploaded(
                    user_id="user-123",
                    project_id="proj-456",
                    file_count=150,
                )

                mock_posthog.capture.assert_called_once_with(
                    distinct_id="user-123",
                    event="ca_codebase_uploaded",
                    properties={
                        "product": "code-atlas",
                        "project_id": "proj-456",
                        "file_count": 150,
                    },
                )

    def test_graph_generated_event(self):
        """Test graph generated event tracking."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)

                PostHogAnalytics.graph_generated(
                    user_id="user-123",
                    project_id="proj-456",
                    entity_count=250,
                    relationship_count=500,
                )

                mock_posthog.capture.assert_called_once_with(
                    distinct_id="user-123",
                    event="ca_graph_generated",
                    properties={
                        "product": "code-atlas",
                        "project_id": "proj-456",
                        "entity_count": 250,
                        "relationship_count": 500,
                    },
                )

    def test_query_run_event(self):
        """Test query run event tracking."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)

                PostHogAnalytics.query_run(
                    user_id="user-123",
                    query_type="cypher",
                    result_count=42,
                )

                mock_posthog.capture.assert_called_once_with(
                    distinct_id="user-123",
                    event="ca_query_run",
                    properties={
                        "product": "code-atlas",
                        "query_type": "cypher",
                        "result_count": 42,
                    },
                )

    def test_session_processed_event(self):
        """Test session processed event tracking."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)

                PostHogAnalytics.session_processed(
                    user_id="user-123",
                    session_id="sess-789",
                    entity_count=25,
                )

                mock_posthog.capture.assert_called_once_with(
                    distinct_id="user-123",
                    event="ca_session_processed",
                    properties={
                        "product": "code-atlas",
                        "session_id": "sess-789",
                        "entity_count": 25,
                    },
                )

    def test_insight_extracted_event(self):
        """Test insight extracted event tracking."""
        from code_atlas.posthog_analytics import PostHogAnalytics

        settings = AtlasSettings(posthog_api_key="phc_test_key")

        with patch("code_atlas.posthog_analytics.HAS_POSTHOG", True):
            with patch("code_atlas.posthog_analytics.posthog") as mock_posthog:
                PostHogAnalytics.initialize(settings)

                PostHogAnalytics.insight_extracted(
                    user_id="user-123",
                    insight_type="decision",
                )

                mock_posthog.capture.assert_called_once_with(
                    distinct_id="user-123",
                    event="ca_insight_extracted",
                    properties={
                        "product": "code-atlas",
                        "insight_type": "decision",
                    },
                )
