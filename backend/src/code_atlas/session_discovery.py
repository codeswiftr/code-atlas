"""Discovery utilities for Claude session files."""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pathspec import PathSpec

from .config import AtlasSettings, SessionFilter
from .models import SessionMetadata


@dataclass(slots=True)
class SessionDiscovery:
    """Discover Claude Code session files under a root directory."""

    root: Path | None = None
    settings: AtlasSettings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or AtlasSettings()
        self.root = (self.root or self.settings.claude_root).expanduser().resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"Claude session root not found: {self.root}")

    def discover(
        self,
        filters: SessionFilter | None = None,
        ignore_patterns: Sequence[str] | None = None,
    ) -> list[SessionMetadata]:
        """Return session metadata objects that satisfy the given filters."""

        compiled_ignore = self._compile_ignore(ignore_patterns, self.settings.ignore_file)
        filt = filters or SessionFilter()
        metadata: list[SessionMetadata] = []

        for session_path in self._iter_session_files():
            if compiled_ignore and self._is_ignored(session_path, compiled_ignore):
                continue

            meta = self._build_metadata(session_path)
            if not self._passes_filters(meta, filt):
                continue

            metadata.append(meta)
            if filt.limit and len(metadata) >= filt.limit:
                break

        return metadata

    def discover_generator(
        self,
        root: Path | None = None,
        project_filter: str | None = None,
        ignore_patterns: Sequence[str] | None = None,
    ) -> Iterator[Path]:
        """Generator that yields session file paths.

        Memory-efficient alternative to discover() that streams results.

        Args:
            root: Override root directory to search
            project_filter: Glob pattern to filter by project name
            ignore_patterns: Additional patterns to ignore

        Yields:
            Path objects for each discovered session file
        """
        search_root = root or self.root
        if not search_root.exists():
            return

        compiled_ignore = self._compile_ignore(ignore_patterns, self.settings.ignore_file)
        pattern = "*.jsonl"

        for path in sorted(search_root.rglob(pattern)):
            # Apply ignore patterns
            if compiled_ignore and self._is_ignored(path, compiled_ignore):
                continue

            # Apply project filter if specified
            if project_filter:
                try:
                    rel_path = path.relative_to(search_root)
                    project_name = rel_path.parts[0] if rel_path.parts else ""
                    if project_filter not in project_name:
                        continue
                except ValueError:
                    continue

            # Skip if path is too deep
            try:
                rel_path = path.relative_to(search_root)
                if len(rel_path.parts) > 3:
                    continue
            except ValueError:
                continue

            yield path

    def _iter_session_files(self) -> Iterator[Path]:
        pattern = "*.jsonl"
        session_dir_name = os.environ.get("CODE_ATLAS_SESSION_DIR", "sessions")
        
        # If CODE_ATLAS_SESSION_DIR is explicitly set, require it in the path
        # Otherwise, allow files directly in project directories OR in sessions subdirectory
        require_sessions_dir = "CODE_ATLAS_SESSION_DIR" in os.environ
        
        for path in sorted(self.root.rglob(pattern)):
            # Skip if sessions directory is required but not found in path
            if require_sessions_dir and session_dir_name not in path.parts:
                continue
            
            # Skip if path is too deep (more than 2 levels from root: project/sessions/file.jsonl)
            # This prevents matching files in nested subdirectories
            rel_path = path.relative_to(self.root)
            depth = len(rel_path.parts)
            
            # Allow: project/file.jsonl (depth=2) or project/sessions/file.jsonl (depth=3)
            if depth > 3:
                continue
            
            # If depth is 3, verify it's in a sessions subdirectory
            if depth == 3 and session_dir_name not in path.parts:
                continue
            
            yield path

    def _build_metadata(self, path: Path) -> SessionMetadata:
        stats = path.stat()
        session_id = path.stem
        rel_parts = path.relative_to(self.root).parts
        project = rel_parts[0] if rel_parts else "unknown"
        modified_at = datetime.fromtimestamp(stats.st_mtime, tz=UTC)

        return SessionMetadata(
            path=path,
            session_id=session_id,
            project=project,
            size_bytes=stats.st_size,
            modified_at=modified_at,
        )

    def _passes_filters(self, meta: SessionMetadata, filt: SessionFilter) -> bool:
        if filt.include_projects and meta.project not in filt.include_projects:
            return False
        if filt.exclude_projects and meta.project in filt.exclude_projects:
            return False
        if filt.modified_after and meta.modified_at.timestamp() <= filt.modified_after:
            return False
        if meta.size_bytes > self.settings.max_session_size_mb * 1024 * 1024:
            return False
        return True

    @staticmethod
    def _compile_ignore(
        inline_patterns: Sequence[str] | None,
        ignore_file: Path | None,
    ) -> PathSpec | None:
        patterns: list[str] = []
        if ignore_file and ignore_file.exists():
            patterns.extend(ignore_file.read_text().splitlines())
        if inline_patterns:
            patterns.extend(inline_patterns)
        if not patterns:
            return None
        return PathSpec.from_lines("gitwildmatch", patterns)

    def _is_ignored(self, path: Path, spec: PathSpec) -> bool:
        rel = path.relative_to(self.root)
        return spec.match_file(str(rel))
