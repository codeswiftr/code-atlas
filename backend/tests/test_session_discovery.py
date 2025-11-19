from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from code_atlas.config import AtlasSettings, SessionFilter
from code_atlas.session_discovery import SessionDiscovery


def _write_session(root: Path, project: str, name: str, minutes_ago: int) -> Path:
    session_dir = root / project / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / f"{name}.jsonl"
    session_path.write_text("{}", encoding="utf-8")
    mtime = datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_ago)
    os.utime(session_path, (mtime.timestamp(), mtime.timestamp()))
    return session_path


def test_discovery_filters_by_project(tmp_path: Path) -> None:
    _write_session(tmp_path, "alpha", "s1", 10)
    _write_session(tmp_path, "beta", "s2", 5)
    discovery = SessionDiscovery(root=tmp_path, settings=AtlasSettings(claude_root=tmp_path))

    results = discovery.discover(filters=SessionFilter(include_projects={"alpha"}))

    assert {meta.project for meta in results} == {"alpha"}


def test_discovery_respects_modified_after(tmp_path: Path) -> None:
    first = _write_session(tmp_path, "alpha", "s1", 60)
    second = _write_session(tmp_path, "alpha", "s2", 5)
    cutoff = datetime.fromtimestamp(first.stat().st_mtime + 1, tz=timezone.utc).timestamp()
    discovery = SessionDiscovery(root=tmp_path, settings=AtlasSettings(claude_root=tmp_path))

    results = discovery.discover(filters=SessionFilter(modified_after=cutoff))

    assert len(results) == 1
    assert results[0].session_id == "s2"


def test_discovery_applies_ignore_file(tmp_path: Path) -> None:
    _write_session(tmp_path, "alpha", "s1", 1)
    ignore_file = tmp_path / ".code-atlas-ignore"
    ignore_file.write_text("alpha/sessions/s1.jsonl", encoding="utf-8")
    settings = AtlasSettings(claude_root=tmp_path, ignore_file=ignore_file)
    discovery = SessionDiscovery(root=tmp_path, settings=settings)

    results = discovery.discover()

    assert results == []


def test_discovery_limit(tmp_path: Path) -> None:
    for idx in range(5):
        _write_session(tmp_path, "alpha", f"s{idx}", minutes_ago=idx)
    discovery = SessionDiscovery(root=tmp_path, settings=AtlasSettings(claude_root=tmp_path))

    results = discovery.discover(filters=SessionFilter(limit=2))

    assert len(results) == 2
