"""Production readiness tests for Code Atlas.

Tests for Dockerfile, health checks, configuration, and deployment.
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

# Get paths
BACKEND_DIR = Path(__file__).parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"


class TestDockerfile:
    """Tests for Dockerfile configuration."""

    def test_dockerfile_exists(self):
        """Verify Dockerfile exists in backend directory."""
        dockerfile = BACKEND_DIR / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile not found in backend/"

    def test_dockerfile_has_required_instructions(self):
        """Verify Dockerfile has required instructions."""
        dockerfile = BACKEND_DIR / "Dockerfile"
        content = dockerfile.read_text()

        # Check for multi-stage build
        assert "FROM" in content, "Missing FROM instruction"
        assert content.count("FROM") >= 2, "Should be multi-stage build (2+ FROM)"

        # Check for security best practices
        assert "USER" in content, "Should run as non-root user"
        assert "HEALTHCHECK" in content, "Should include HEALTHCHECK"
        assert "EXPOSE" in content, "Should EXPOSE port"

    def test_dockerfile_exposes_correct_port(self):
        """Verify Dockerfile exposes port 8000."""
        dockerfile = BACKEND_DIR / "Dockerfile"
        content = dockerfile.read_text()
        assert "EXPOSE 8000" in content, "Should expose port 8000"

    def test_dockerfile_uses_slim_base(self):
        """Verify Dockerfile uses slim base image for smaller size."""
        dockerfile = BACKEND_DIR / "Dockerfile"
        content = dockerfile.read_text()
        assert "python:3.11-slim" in content, "Should use slim base image"


class TestDockerCompose:
    """Tests for docker-compose configurations."""

    def test_dev_compose_exists(self):
        """Verify development docker-compose exists."""
        compose = BACKEND_DIR / "docker-compose.yml"
        assert compose.exists(), "docker-compose.yml not found"

    def test_prod_compose_exists(self):
        """Verify production docker-compose exists."""
        compose = BACKEND_DIR / "docker-compose.prod.yml"
        assert compose.exists(), "docker-compose.prod.yml not found"

    def test_prod_compose_has_all_services(self):
        """Verify production compose has required services."""
        compose = BACKEND_DIR / "docker-compose.prod.yml"
        content = compose.read_text()

        assert "falkordb:" in content, "Missing FalkorDB service"
        assert "api:" in content, "Missing API service"

    def test_prod_compose_has_health_checks(self):
        """Verify production compose has health checks."""
        compose = BACKEND_DIR / "docker-compose.prod.yml"
        content = compose.read_text()
        assert "healthcheck:" in content, "Missing health checks"

    def test_prod_compose_has_volumes(self):
        """Verify production compose persists data."""
        compose = BACKEND_DIR / "docker-compose.prod.yml"
        content = compose.read_text()
        assert "volumes:" in content, "Missing volume configuration"


class TestHealthCheckScript:
    """Tests for health-check.sh script."""

    def test_health_check_script_exists(self):
        """Verify health check script exists."""
        script = SCRIPTS_DIR / "health-check.sh"
        assert script.exists(), "health-check.sh not found"

    def test_health_check_script_executable(self):
        """Verify health check script is executable."""
        script = SCRIPTS_DIR / "health-check.sh"
        assert os.access(script, os.X_OK), "health-check.sh should be executable"

    def test_health_check_script_has_help(self):
        """Verify health check script has help option."""
        script = SCRIPTS_DIR / "health-check.sh"
        result = subprocess.run(
            ["bash", str(script), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Help should exit with 0"
        assert "Usage:" in result.stdout, "Help should include usage"


class TestBackupScript:
    """Tests for backup.sh script."""

    def test_backup_script_exists(self):
        """Verify backup script exists."""
        script = SCRIPTS_DIR / "backup.sh"
        assert script.exists(), "backup.sh not found"

    def test_backup_script_executable(self):
        """Verify backup script is executable."""
        script = SCRIPTS_DIR / "backup.sh"
        assert os.access(script, os.X_OK), "backup.sh should be executable"

    def test_backup_script_has_help(self):
        """Verify backup script has help option."""
        script = SCRIPTS_DIR / "backup.sh"
        result = subprocess.run(
            ["bash", str(script), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Help should exit with 0"
        assert "Usage:" in result.stdout, "Help should include usage"


class TestRestoreScript:
    """Tests for restore.sh script."""

    def test_restore_script_exists(self):
        """Verify restore script exists."""
        script = SCRIPTS_DIR / "restore.sh"
        assert script.exists(), "restore.sh not found"

    def test_restore_script_executable(self):
        """Verify restore script is executable."""
        script = SCRIPTS_DIR / "restore.sh"
        assert os.access(script, os.X_OK), "restore.sh should be executable"

    def test_restore_script_has_help(self):
        """Verify restore script has help option."""
        script = SCRIPTS_DIR / "restore.sh"
        result = subprocess.run(
            ["bash", str(script), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Help should exit with 0"
        assert "Usage:" in result.stdout, "Help should include usage"


class TestGitHubActions:
    """Tests for GitHub Actions workflows."""

    def test_ci_workflow_exists(self):
        """Verify CI workflow exists."""
        workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        assert workflow.exists(), "CI workflow not found"

    def test_cd_workflow_exists(self):
        """Verify CD workflow exists."""
        workflow = PROJECT_ROOT / ".github" / "workflows" / "cd.yml"
        assert workflow.exists(), "CD workflow not found"

    def test_ci_workflow_has_test_job(self):
        """Verify CI workflow has test job."""
        workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        content = workflow.read_text()
        assert "backend-test:" in content, "Missing backend test job"
        assert "pytest" in content, "Should run pytest"

    def test_ci_workflow_has_lint_job(self):
        """Verify CI workflow has lint job."""
        workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        content = workflow.read_text()
        assert "backend-lint:" in content, "Missing lint job"
        assert "ruff" in content, "Should run ruff"

    def test_cd_workflow_builds_docker(self):
        """Verify CD workflow builds Docker image."""
        workflow = PROJECT_ROOT / ".github" / "workflows" / "cd.yml"
        content = workflow.read_text()
        assert "docker" in content.lower(), "Should build Docker image"
        assert "ghcr.io" in content, "Should push to GitHub Container Registry"


class TestProductionConfiguration:
    """Tests for production configuration."""

    def test_env_example_exists(self):
        """Verify .env.example exists."""
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists(), ".env.example not found"

    def test_env_example_has_required_vars(self):
        """Verify .env.example has required variables."""
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text()

        required_vars = [
            "CODE_ATLAS_API_KEY_REQUIRED",
            "CODE_ATLAS_ADMIN_API_KEY",
            "CODE_ATLAS_REDIS_URL",
            "CODE_ATLAS_LOG_LEVEL",
        ]

        for var in required_vars:
            assert var in content, f"Missing {var} in .env.example"

    def test_makefile_exists(self):
        """Verify Makefile exists."""
        makefile = PROJECT_ROOT / "Makefile"
        assert makefile.exists(), "Makefile not found"

    def test_makefile_has_common_targets(self):
        """Verify Makefile has common targets."""
        makefile = PROJECT_ROOT / "Makefile"
        content = makefile.read_text()

        targets = ["setup", "dev", "test", "lint", "docker-up"]
        for target in targets:
            assert f"{target}:" in content, f"Missing {target} target in Makefile"


class TestAPIHealthEndpoint:
    """Tests for API health endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient

        from code_atlas.api.main import create_app
        from code_atlas.config import AtlasSettings

        settings = AtlasSettings()
        app = create_app(settings)
        return TestClient(app)

    def test_health_endpoint_exists(self, client):
        """Verify /health endpoint exists."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_status(self, client):
        """Verify /health returns status field."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy", "degraded"]
