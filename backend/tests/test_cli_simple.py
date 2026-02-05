"""Simple CLI tests to verify basic functionality works.

This is a simplified test file that tests CLI commands with minimal dependencies.

NOTE: These tests require KMP_DUPLICATE_LIB_OK=TRUE environment variable
to avoid OpenMP conflicts with sentence-transformers library.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

# Set OpenMP workaround
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


def run_cli_command(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a CLI command and return (exit_code, stdout, stderr)."""
    try:
        env = os.environ.copy()
        env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        result = subprocess.run(
            ["uv", "run", "code-atlas"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent.parent,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        pytest.fail(f"Command timed out: code-atlas {' '.join(args)}")


def test_cli_help() -> None:
    """Test that CLI help works."""
    exit_code, stdout, stderr = run_cli_command(["--help"])
    assert exit_code == 0
    assert "Utilities for turning Claude sessions" in stdout


def test_discover_help() -> None:
    """Test discover command help."""
    exit_code, stdout, stderr = run_cli_command(["discover", "--help"])
    assert exit_code == 0
    assert "List discovered sessions" in stdout


def test_index_help() -> None:
    """Test index command help."""
    exit_code, stdout, stderr = run_cli_command(["index", "--help"])
    assert exit_code == 0
    assert "Index Claude Code sessions" in stdout


def test_query_help() -> None:
    """Test query command help."""
    exit_code, stdout, stderr = run_cli_command(["query", "--help"])
    assert exit_code == 0
    assert "Query the knowledge graph" in stdout


def test_export_help() -> None:
    """Test export command help."""
    exit_code, stdout, stderr = run_cli_command(["export", "--help"])
    assert exit_code == 0
    assert "Export knowledge graph data" in stdout


def test_status_help() -> None:
    """Test status command help."""
    exit_code, stdout, stderr = run_cli_command(["status", "--help"])
    assert exit_code == 0
    assert "Show status of the Code Atlas knowledge graph" in stdout


def test_report_help() -> None:
    """Test report command help."""
    exit_code, stdout, stderr = run_cli_command(["report", "--help"])
    assert exit_code == 0
    assert "Generate summary report" in stdout


def test_indexes_help() -> None:
    """Test indexes command help."""
    exit_code, stdout, stderr = run_cli_command(["indexes", "--help"])
    assert exit_code == 0
    assert "Manage database indexes" in stdout


def test_metrics_help() -> None:
    """Test metrics command help."""
    exit_code, stdout, stderr = run_cli_command(["metrics", "--help"])
    assert exit_code == 0
    assert "Start the Prometheus metrics server" in stdout


def test_serve_help() -> None:
    """Test serve command help."""
    exit_code, stdout, stderr = run_cli_command(["serve", "--help"])
    assert exit_code == 0
    assert "Start the Code Atlas API server" in stdout


def test_run_help() -> None:
    """Test run command (legacy alias) help."""
    exit_code, stdout, stderr = run_cli_command(["run", "--help"])
    assert exit_code == 0
    assert "Code Atlas pipeline" in stdout
