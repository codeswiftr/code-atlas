#!/usr/bin/env python3
"""Environment variable validation script for Code Atlas.

Usage:
    python scripts/validate-env.py
    python scripts/validate-env.py --env production
    python scripts/validate-env.py --strict

Exit codes:
    0: All required variables set
    1: Missing required variables
    2: Invalid variable values
"""

import os
import sys
from pathlib import Path

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


class EnvValidator:
    """Validates environment variables for Code Atlas."""

    # Required variables for all environments
    REQUIRED_ALWAYS: list[str] = [
        "FALKORDB_HOST",
        "FALKORDB_PORT",
    ]

    # Required for production environment
    REQUIRED_PRODUCTION: list[str] = [
        "CODE_ATLAS_ADMIN_API_KEY",
        "CODE_ATLAS_JWT_SECRET",
    ]

    # Recommended but not required
    RECOMMENDED: list[str] = [
        "ANTHROPIC_API_KEY",  # Or OPENROUTER_API_KEY
        "CODE_ATLAS_LOG_FILE",
        "POSTHOG_API_KEY",
    ]

    # Valid values for specific variables
    VALID_VALUES: dict[str, list[str]] = {
        "CODE_ATLAS_ENV": ["development", "staging", "production"],
        "CODE_ATLAS_LOG_LEVEL": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        "CODE_ATLAS_LOG_FORMAT": ["json", "text"],
    }

    # Boolean variables
    BOOLEAN_VARS: list[str] = [
        "CODE_ATLAS_API_KEY_REQUIRED",
        "CODE_ATLAS_ENABLE_METRICS",
        "CODE_ATLAS_ENABLE_CORS",
        "CODE_ATLAS_ENABLE_RATE_LIMIT",
        "CODE_ATLAS_DEBUG",
        "CODE_ATLAS_RELOAD",
    ]

    # Numeric variables with ranges
    NUMERIC_RANGES: dict[str, tuple[float, float]] = {
        "CODE_ATLAS_PORT": (1, 65535),
        "FALKORDB_PORT": (1, 65535),
        "CODE_ATLAS_MAX_SESSIONS": (1, 10000),
        "CODE_ATLAS_WORKER_THREADS": (1, 32),
        "CODE_ATLAS_DEDUP_SIMILARITY_THRESHOLD": (0.0, 1.0),
        "CODE_ATLAS_RATE_LIMIT_STANDARD": (1, 100000),
        "CODE_ATLAS_RATE_LIMIT_ADMIN": (1, 100000),
    }

    def __init__(self, env: str = "development", strict: bool = False):
        """Initialize validator.

        Args:
            env: Target environment (development, staging, production)
            strict: If True, treat warnings as errors
        """
        self.env = env
        self.strict = strict
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []

    def validate(self) -> bool:
        """Run all validations.

        Returns:
            True if all validations pass, False otherwise
        """
        print(f"{BOLD}{BLUE}Code Atlas Environment Validation{RESET}")
        print(f"Environment: {BOLD}{self.env}{RESET}")
        print(f"Strict mode: {BOLD}{self.strict}{RESET}\n")

        # Check required variables
        self._check_required_variables()

        # Check recommended variables
        self._check_recommended_variables()

        # Validate variable values
        self._validate_variable_values()

        # Check boolean variables
        self._check_boolean_variables()

        # Check numeric ranges
        self._check_numeric_ranges()

        # Print results
        self._print_results()

        # Determine success
        has_errors = len(self.errors) > 0
        has_warnings = len(self.warnings) > 0

        if has_errors:
            return False

        if self.strict and has_warnings:
            print(f"\n{YELLOW}Strict mode: Treating warnings as errors{RESET}")
            return False

        return True

    def _check_required_variables(self) -> None:
        """Check that all required variables are set."""
        required = self.REQUIRED_ALWAYS.copy()

        if self.env == "production":
            required.extend(self.REQUIRED_PRODUCTION)

        for var in required:
            value = os.getenv(var)
            if not value:
                self.errors.append(f"Missing required variable: {var}")
            else:
                self.passed.append(f"Required variable set: {var}")

    def _check_recommended_variables(self) -> None:
        """Check recommended variables."""
        for var in self.RECOMMENDED:
            value = os.getenv(var)
            if not value:
                # Special case: Either ANTHROPIC_API_KEY or OPENROUTER_API_KEY
                if var == "ANTHROPIC_API_KEY":
                    if not os.getenv("OPENROUTER_API_KEY"):
                        self.warnings.append(
                            f"Recommended: Set {var} or OPENROUTER_API_KEY for AI-powered extraction"
                        )
                else:
                    self.warnings.append(f"Recommended: Set {var}")
            else:
                self.passed.append(f"Recommended variable set: {var}")

    def _validate_variable_values(self) -> None:
        """Validate that variables have valid values."""
        for var, valid_values in self.VALID_VALUES.items():
            value = os.getenv(var)
            if value and value not in valid_values:
                self.errors.append(
                    f"Invalid value for {var}: '{value}'. Valid values: {', '.join(valid_values)}"
                )
            elif value:
                self.passed.append(f"Valid value for {var}: {value}")

    def _check_boolean_variables(self) -> None:
        """Check boolean variables have valid values."""
        for var in self.BOOLEAN_VARS:
            value = os.getenv(var, "").lower()
            if value and value not in ["true", "false", "1", "0", "yes", "no"]:
                self.errors.append(
                    f"Invalid boolean value for {var}: '{value}'. Use: true/false, 1/0, yes/no"
                )

    def _check_numeric_ranges(self) -> None:
        """Check numeric variables are within valid ranges."""
        for var, (min_val, max_val) in self.NUMERIC_RANGES.items():
            value_str = os.getenv(var)
            if not value_str:
                continue

            try:
                value = float(value_str)
                if value < min_val or value > max_val:
                    self.errors.append(
                        f"{var} out of range: {value} (must be between {min_val} and {max_val})"
                    )
                else:
                    self.passed.append(f"{var} in valid range: {value}")
            except ValueError:
                self.errors.append(f"Invalid numeric value for {var}: '{value_str}'")

    def _print_results(self) -> None:
        """Print validation results."""
        print(f"\n{BOLD}Validation Results:{RESET}")
        print(f"{GREEN}Passed: {len(self.passed)}{RESET}")
        print(f"{YELLOW}Warnings: {len(self.warnings)}{RESET}")
        print(f"{RED}Errors: {len(self.errors)}{RESET}\n")

        if self.errors:
            print(f"{BOLD}{RED}Errors:{RESET}")
            for error in self.errors:
                print(f"  {RED}✗{RESET} {error}")
            print()

        if self.warnings:
            print(f"{BOLD}{YELLOW}Warnings:{RESET}")
            for warning in self.warnings:
                print(f"  {YELLOW}!{RESET} {warning}")
            print()

        # Only show passed in verbose mode
        if not self.errors and not self.warnings:
            print(f"{GREEN}All validations passed!{RESET}")


def load_env_file(env_file: Path | None = None) -> None:
    """Load environment variables from .env file.

    Args:
        env_file: Path to .env file. If None, looks for .env in current directory.
    """
    if env_file is None:
        env_file = Path(".env")

    if not env_file.exists():
        print(f"{YELLOW}Warning: .env file not found at {env_file}{RESET}")
        print(f"{YELLOW}Using environment variables from shell{RESET}\n")
        return

    print(f"Loading environment from: {env_file}\n")

    with open(env_file) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value


def print_suggestions(env: str) -> None:
    """Print helpful suggestions based on environment.

    Args:
        env: Target environment
    """
    print(f"\n{BOLD}{BLUE}Suggestions for {env} environment:{RESET}\n")

    if env == "production":
        print("Production checklist:")
        print("  • Set CODE_ATLAS_ENV=production")
        print("  • Set CODE_ATLAS_API_KEY_REQUIRED=true")
        print("  • Set CODE_ATLAS_LOG_FORMAT=json")
        print("  • Set CODE_ATLAS_DEBUG=false")
        print("  • Configure CORS_ORIGINS (not '*')")
        print("  • Generate secure JWT_SECRET:")
        print(f'    {BLUE}python -c "import secrets; print(secrets.token_urlsafe(32))"{RESET}')
        print("  • Generate admin API key:")
        print(
            f"    {BLUE}python -c \"import secrets; print('sk-' + secrets.token_urlsafe(32))\"{RESET}"
        )

    elif env == "development":
        print("Development setup:")
        print("  • Set CODE_ATLAS_ENV=development")
        print("  • Set CODE_ATLAS_RELOAD=true for auto-reload")
        print("  • Set CODE_ATLAS_DEBUG=true for detailed errors")
        print("  • Use CODE_ATLAS_CORS_ORIGINS=*")
        print("  • API key optional (CODE_ATLAS_API_KEY_REQUIRED=false)")

    print(f"\n{BOLD}Example .env file:{RESET}")
    print(f"  {BLUE}cp .env.example .env{RESET}")
    print(f"  {BLUE}nano .env{RESET} (edit required values)")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 = success, 1 = validation failed)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate Code Atlas environment variables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env",
        choices=["development", "staging", "production"],
        default=os.getenv("CODE_ATLAS_ENV", "development"),
        help="Target environment (default: development)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Path to .env file (default: .env in current directory)",
    )
    parser.add_argument(
        "--suggestions",
        action="store_true",
        help="Show environment-specific suggestions",
    )

    args = parser.parse_args()

    # Load .env file
    load_env_file(args.env_file)

    # Run validation
    validator = EnvValidator(env=args.env, strict=args.strict)
    success = validator.validate()

    # Show suggestions if requested or if validation failed
    if args.suggestions or not success:
        print_suggestions(args.env)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
