"""Discovery utilities for Claude session files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

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

    def _iter_session_files(self) -> Iterator[Path]:
        pattern = "*.jsonl"
        session_dir_name = os.environ.get("CODE_ATLAS_SESSION_DIR", "sessions")
        for path in sorted(self.root.rglob(pattern)):
            if session_dir_name not in path.parts:
                continue
            yield path

    def _build_metadata(self, path: Path) -> SessionMetadata:
        stats = path.stat()
        session_id = path.stem
        rel_parts = path.relative_to(self.root).parts
        project = rel_parts[0] if rel_parts else "unknown"
        modified_at = datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc)

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
