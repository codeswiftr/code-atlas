"""Tests for configuration loading (TOML + environment variables)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from code_atlas.config import AtlasSettings


@pytest.fixture
def sample_toml() -> str:
    """Valid TOML configuration."""
    return """
[discovery]
claude_root = "~/test-projects"
max_session_size_mb = 100

[extraction]
use_llm = true
model = "claude-3-5-sonnet-latest"
max_cost_per_session_usd = 0.05

[graph]
graph_name = "test_atlas"
redis_url = "redis://testhost:6380"

[pipeline]
max_retries = 5
max_cumulative_cost_usd = 20.0
"""


@pytest.fixture
def invalid_toml() -> str:
    """Malformed TOML."""
    return """
[discovery
claude_root = "~/test"  # Missing closing bracket
"""


class TestTOMLLoading:
    """Test TOML configuration loading."""

    def test_load_from_toml(self, sample_toml: str, tmp_path: Path) -> None:
        """Test loading settings from TOML file."""
        config_file = tmp_path / "test.toml"
        config_file.write_text(sample_toml)

        settings = AtlasSettings.from_toml(config_file)

        # Paths should be fully expanded and resolved
        expected_path = Path("~/test-projects").expanduser().resolve()
        assert settings.claude_root == expected_path
        assert settings.max_session_size_mb == 100
        assert settings.max_cost_per_session_usd == 0.05
        assert settings.max_cumulative_cost_usd == 20.0

    def test_missing_toml_file(self) -> None:
        """Test handling of missing TOML file."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            AtlasSettings.from_toml("/nonexistent/config.toml")

    def test_invalid_toml(self, invalid_toml: str, tmp_path: Path) -> None:
        """Test handling of malformed TOML."""
        config_file = tmp_path / "bad.toml"
        config_file.write_text(invalid_toml)

        with pytest.raises(Exception, match="."):  # tomllib.TOMLDecodeError
            AtlasSettings.from_toml(config_file)

    def test_partial_toml(self, tmp_path: Path) -> None:
        """Test TOML with only some sections uses defaults for rest."""
        partial_toml = """
[discovery]
max_session_size_mb = 75
"""
        config_file = tmp_path / "partial.toml"
        config_file.write_text(partial_toml)

        settings = AtlasSettings.from_toml(config_file)

        # Explicitly set value
        assert settings.max_session_size_mb == 75

        # Should use defaults
        assert settings.max_cost_per_session_usd == 0.02
        assert settings.max_cumulative_cost_usd == 10.0

    def test_tilde_expansion(self, tmp_path: Path) -> None:
        """Test that ~ gets expanded in paths."""
        toml = """
[discovery]
claude_root = "~/my-projects"
"""
        config_file = tmp_path / "test.toml"
        config_file.write_text(toml)

        settings = AtlasSettings.from_toml(config_file)

        assert "~" not in str(settings.claude_root)
        assert settings.claude_root.is_absolute()


class TestEnvironmentOverrides:
    """Test environment variable overrides of TOML."""

    def test_env_overrides_toml(
        self, sample_toml: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that environment variables override TOML values."""
        config_file = tmp_path / "test.toml"
        config_file.write_text(sample_toml)

        # Clear any existing CODE_ATLAS env vars that could interfere
        for key in list(os.environ.keys()):
            if key.startswith("CODE_ATLAS_"):
                monkeypatch.delenv(key, raising=False)

        # Set env var that conflicts with TOML
        monkeypatch.setenv("CODE_ATLAS_MAX_SESSION_MB", "200")
        monkeypatch.setenv("CODE_ATLAS_MAX_COST_PER_SESSION", "0.10")

        settings = AtlasSettings.from_toml_with_env_override(config_file)

        # Env vars should win
        assert settings.max_session_size_mb == 200
        assert settings.max_cost_per_session_usd == 0.10

        # Non-overridden values from TOML
        assert settings.max_cumulative_cost_usd == 20.0

    def test_env_only_no_toml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading from environment variables only."""
        monkeypatch.setenv("CODE_ATLAS_CLAUDE_ROOT", "/custom/path")
        monkeypatch.setenv("CODE_ATLAS_MAX_SESSION_MB", "150")

        settings = AtlasSettings()

        assert settings.claude_root == Path("/custom/path")
        assert settings.max_session_size_mb == 150

    def test_no_env_no_toml_uses_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that defaults work when no TOML or env vars."""
        # Clear any existing CODE_ATLAS env vars
        for key in list(os.environ.keys()):
            if key.startswith("CODE_ATLAS_"):
                monkeypatch.delenv(key, raising=False)

        settings = AtlasSettings()

        assert settings.claude_root == Path("~/.claude/projects").expanduser()
        assert settings.max_session_size_mb == 50
        assert settings.max_cost_per_session_usd == 0.02
        assert settings.max_cumulative_cost_usd == 10.0


class TestValidation:
    """Test Pydantic validation rules."""

    def test_negative_values_rejected(self, tmp_path: Path) -> None:
        """Test that negative values for size/cost are rejected."""
        bad_toml = """
[discovery]
max_session_size_mb = -10
"""
        config_file = tmp_path / "bad.toml"
        config_file.write_text(bad_toml)

        with pytest.raises(Exception, match="."):  # Pydantic validation error
            AtlasSettings.from_toml(config_file)

    def test_zero_values_allowed(self, tmp_path: Path) -> None:
        """Test that zero is allowed for cost limits (unlimited)."""
        toml = """
[extraction]
max_cost_per_session_usd = 0.0
max_cumulative_cost_usd = 0.0
"""
        config_file = tmp_path / "zero.toml"
        config_file.write_text(toml)

        settings = AtlasSettings.from_toml(config_file)

        assert settings.max_cost_per_session_usd == 0.0
        assert settings.max_cumulative_cost_usd == 0.0
