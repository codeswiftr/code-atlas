"""
Simplified pattern history using append-only JSONL.

Tracks CLI command successes/failures for compounding pattern learning.
Adapted from FORGE harness SimpleHistory for code-atlas CLI.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class SimpleHistory:
    """
    Simplified pattern history using append-only JSONL.

    Records action outcomes and provides basic pattern matching for decision support.
    Thread-safe through append-only writes. No external dependencies.
    """

    def __init__(self, history_file: Optional[Path] = None):
        """
        Initialize history tracker.

        Args:
            history_file: Path to JSONL history file. Defaults to .forge/state/code_atlas_history.jsonl
        """
        if history_file is None:
            self.history_file = Path.cwd() / ".forge" / "state" / "code_atlas_history.jsonl"
        else:
            self.history_file = Path(history_file)

        # Ensure directory exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Create file if it doesn't exist
        if not self.history_file.exists():
            self.history_file.touch()

    def record(
        self,
        domain: str,
        project: str,
        action: str,
        success: bool,
        context: Optional[dict] = None
    ) -> None:
        """
        Record an action outcome.

        Args:
            domain: Domain name (e.g., 'code-atlas')
            project: Project name (e.g., 'sessions')
            action: Action type (e.g., 'extract', 'query', 'visualize')
            success: Whether action succeeded
            context: Optional context data (error message, duration, entity count, etc.)
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": domain,
            "project": project,
            "action": action,
            "success": success,
            "context": context or {}
        }

        # Append to JSONL file (atomic write)
        with open(self.history_file, "a") as f:
            f.write(json.dumps(record) + "\n")

    def get_success_rate(self, domain: str, action: str, limit: int = 10) -> float:
        """
        Calculate success rate for recent matching actions.

        Args:
            domain: Domain to filter by
            action: Action type to filter by
            limit: Number of recent records to consider

        Returns:
            Success rate as float 0.0-1.0, or 0.5 if no history
        """
        matching = self._get_matching_records(domain, action, limit)

        if not matching:
            return 0.5  # Neutral default when no history

        successes = sum(1 for r in matching if r["success"])
        return successes / len(matching)

    def get_recent_patterns(
        self,
        domain: str,
        action: str,
        limit: int = 5
    ) -> list[dict]:
        """
        Get recent successful patterns for context.

        Args:
            domain: Domain to filter by
            action: Action type to filter by
            limit: Number of successful records to return

        Returns:
            List of successful record dicts with timestamp, context, etc.
        """
        matching = self._get_matching_records(domain, action, limit * 2)
        successful = [r for r in matching if r["success"]]
        return successful[:limit]

    def should_proceed(
        self,
        domain: str,
        action: str,
        threshold: float = 0.6
    ) -> tuple[bool, float]:
        """
        Simple decision helper based on historical success rate.

        Args:
            domain: Domain to check
            action: Action type to check
            threshold: Minimum success rate to proceed (default 0.6)

        Returns:
            Tuple of (should_proceed, success_rate)
        """
        success_rate = self.get_success_rate(domain, action)
        return (success_rate >= threshold, success_rate)

    def _get_matching_records(
        self,
        domain: str,
        action: str,
        limit: int
    ) -> list[dict]:
        """
        Get matching records from history file.

        Reads file in reverse to get most recent records first.
        """
        if not self.history_file.exists():
            return []

        matching = []

        # Read file in reverse for most recent records
        with open(self.history_file, "r") as f:
            lines = f.readlines()

        for line in reversed(lines):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
                # Validate required fields
                if (record["domain"] == domain and
                    record["action"] == action and
                    "success" in record):
                    matching.append(record)
                    if len(matching) >= limit:
                        break
            except (json.JSONDecodeError, KeyError):
                continue  # Skip malformed lines

        return matching
