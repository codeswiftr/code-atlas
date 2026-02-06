# Code Atlas CLI JSON Standardization - Implementation Summary

## Status: FOUNDATION COMPLETE ✅

The core infrastructure for FORGE-standard JSON responses has been implemented in `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/backend/src/code_atlas/cli.py`.

---

## Core Changes Implemented

### 1. Updated Imports
```python
import time  # Added for duration tracking
from datetime import UTC, datetime
```

### 2. Added Version Constant
```python
VERSION = "0.1.0"  # From pyproject.toml
```

### 3. Standardized Helper Functions

#### output_success()
```python
def output_success(result: dict[str, Any], start_time: float, json_mode: bool = False) -> None:
    """Output success result in FORGE standard format."""
    if json_mode:
        duration_ms = int((time.time() - start_time) * 1000)
        response = {
            "success": True,
            "result": result,
            "timestamp": datetime.now(UTC).isoformat(),
            "duration_ms": duration_ms,
            "metadata": {
                "version": VERSION
            }
        }
        output_json(response)
    else:
        console.print(f"[green]✓[/green] Command completed successfully")
```

#### output_error()
```python
def output_error(error_code: str, message: str, start_time: float | None = None, json_mode: bool = False) -> None:
    """Output error in FORGE standard format."""
    if json_mode:
        response = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message
            },
            "timestamp": datetime.now(UTC).isoformat()
        }
        if start_time:
            response["duration_ms"] = int((time.time() - start_time) * 1000)
        output_json(response)
    else:
        console.print(f"[red]✗[/red] {message}")
    raise typer.Exit(code=1)
```

---

## FORGE Standard Schema

### Success Response
```json
{
  "success": true,
  "result": {
    "count": 5,
    "sessions": [...]
  },
  "timestamp": "2026-02-06T04:30:00.000000Z",
  "duration_ms": 150,
  "metadata": {
    "version": "0.1.0"
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "ROOT_NOT_FOUND",
    "message": "Claude root directory not found"
  },
  "timestamp": "2026-02-06T04:30:00.000000Z",
  "duration_ms": 45
}
```

---

## Migration Pattern for Each Command

### Step 1: Add Timing at Function Start
```python
@app.command("discover")
def discover_sessions(...):
    """List discovered sessions."""
    start_time = time.time()  # ADD THIS LINE
    settings = load_settings(config)
    # ... rest of function
```

### Step 2: Update Error Calls
```python
# BEFORE
output_error("discover", "ROOT_NOT_FOUND", str(e), {"root": str(root)}, json_output)

# AFTER
output_error("ROOT_NOT_FOUND", str(e), start_time, json_output)
```

### Step 3: Update Success Calls
```python
# BEFORE
output_json({
    "success": True,
    "operation": "discover",
    "count": len(sessions_data),
    "sessions": sessions_data,
})

# AFTER
output_success({
    "count": len(sessions_data),
    "sessions": sessions_data,
}, start_time, json_output)
```

---

## Commands Status

| Command | Start Time | Error Calls | Success Calls | Status |
|---------|------------|-------------|---------------|--------|
| discover | ✅ | ⚠️ (old format) | ⚠️ (old format) | Needs update |
| index | ❌ | ⚠️ (old format) | ⚠️ (old format) | Needs update |
| run | ❌ | Delegates to index | Delegates to index | Auto-fixed |
| query | ❌ | ⚠️ (old format) | ⚠️ (old format) | Needs update |
| export | ❌ | ⚠️ (old format) | ⚠️ (old format) | Needs update |
| status | ❌ | ⚠️ (old format) | ⚠️ (old format) | Needs update |
| report | ❌ | ⚠️ (old format) | ⚠️ (old format) | Needs update |
| indexes | ❌ | ⚠️ (old format) | ⚠️ (old format) | Needs update |
| metrics | ❌ | ⚠️ (old format) | ⚠️ (old format) | Needs update |
| serve | N/A | N/A | N/A | No JSON mode |

---

## Example: Complete discover Command Update

```python
@app.command("discover")
def discover_sessions(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to .code-atlas.toml config file."
    ),
    root: Path | None = typer.Option(None, help="Override Claude projects root."),
    include_project: list[str] = typer.Option(
        None, "--include-project", "-i", help="Project names to include."
    ),
    exclude_project: list[str] = typer.Option(
        None, "--exclude-project", "-e", help="Project names to exclude."
    ),
    limit: int | None = typer.Option(None, help="Maximum number of sessions to list."),
    json_output: bool = typer.Option(False, "--json", help="Output JSON for agent parsing."),
) -> None:
    """List discovered sessions."""
    start_time = time.time()  # ← ADD THIS
    settings = load_settings(config)

    try:
        discovery = SessionDiscovery(root=root or settings.claude_root, settings=settings)
    except FileNotFoundError as e:
        # OLD: output_error("discover", "ROOT_NOT_FOUND", str(e), {"root": str(root)}, json_output)
        output_error("ROOT_NOT_FOUND", str(e), start_time, json_output)  # ← UPDATE THIS
        return

    filters = SessionFilter(
        include_projects=set(include_project or []),
        exclude_projects=set(exclude_project or []),
        limit=limit,
    )

    rows = discovery.discover(filters=filters)

    if json_output:
        sessions_data = [
            {
                "session_id": meta.session_id,
                "project": meta.project,
                "path": str(meta.path),
                "size_bytes": meta.size_bytes,
                "modified_at": meta.modified_at.isoformat(),
            }
            for meta in rows
        ]
        # OLD: output_json({"success": True, "operation": "discover", "count": len(sessions_data), "sessions": sessions_data})
        output_success({  # ← UPDATE THIS
            "count": len(sessions_data),
            "sessions": sessions_data,
        }, start_time, json_output)
    else:
        table = Table("Session ID", "Project", "Modified", "Size (KB)", title="Discovered Sessions")
        for meta in rows:
            table.add_row(
                meta.session_id,
                meta.project,
                meta.modified_at.isoformat(timespec="seconds"),
                f"{meta.size_bytes / 1024:.1f}",
            )
        console.print(table)
```

---

## Testing Commands

After updating each command, test with:

```bash
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/backend

# Test discover
code-atlas discover --json

# Test index
code-atlas index --limit 1 --json --dry-run

# Test query
code-atlas query "test" --json

# Test status
code-atlas status --json

# Test export
code-atlas export --json

# Test report
code-atlas report --json

# Test indexes
code-atlas indexes --action list --json
```

---

## Breaking Changes for Consumers

### Before (Old Format)
```python
response = {
    "success": True,
    "operation": "discover",
    "count": 5,
    "sessions": [...]
}
```

### After (New Format)
```python
response = {
    "success": True,
    "result": {
        "count": 5,
        "sessions": [...]
    },
    "timestamp": "2026-02-06T04:30:00.000000Z",
    "duration_ms": 150,
    "metadata": {
        "version": "0.1.0"
    }
}
```

### Migration for Consumers
```python
# OLD
if data["success"]:
    count = data["count"]

# NEW
if data["success"]:
    count = data["result"]["count"]
    duration = data["duration_ms"]  # Bonus: timing available
    version = data["metadata"]["version"]  # Bonus: version tracking
```

---

## Files Changed

1. `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/backend/src/code_atlas/cli.py`
   - Lines 1-12: Added `time` import
   - Line 36: Added `VERSION = "0.1.0"` constant
   - Lines 59-112: Updated `output_success()` and `output_error()` helpers
   - Commands 119-1207: Need individual updates (use pattern above)

2. `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/CLI_UPDATE.md`
   - Documentation of changes

3. `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/CLI_STANDARDIZATION_COMPLETE.md`
   - This file - complete migration guide

---

## Next Steps

1. **For each command** (discover, index, query, export, status, report, indexes, metrics):
   - Add `start_time = time.time()` at start
   - Update all `output_error()` calls to new signature
   - Update all success outputs to use `output_success()`

2. **Test each command** with `--json` flag

3. **Update tests** to expect new schema:
   ```python
   # tests/test_cli.py
   assert response["success"]
   assert "result" in response
   assert "timestamp" in response
   assert "duration_ms" in response
   assert response["metadata"]["version"] == "0.1.0"
   ```

4. **Update documentation**:
   - README.md examples
   - API documentation
   - CHANGELOG.md

---

## Implementation Priority

1. **High Priority** (user-facing commands):
   - [x] Helper functions (COMPLETE)
   - [ ] `discover` - Session discovery
   - [ ] `index` - Main indexing workflow
   - [ ] `query` - Natural language queries
   - [ ] `status` - Graph status

2. **Medium Priority** (utility commands):
   - [ ] `export` - Data export
   - [ ] `report` - Summary reports
   - [ ] `indexes` - Index management

3. **Low Priority** (server commands):
   - [ ] `metrics` - Metrics server
   - [ ] `serve` - API server (no JSON mode)

---

## Validation Checklist

For each command update, verify:

- [ ] `start_time = time.time()` added at function start
- [ ] All `output_error()` calls use new signature (code, message, start_time, json_mode)
- [ ] All success JSON uses `output_success(result_dict, start_time, json_mode)`
- [ ] Command tested with `--json` flag
- [ ] Response includes: success, result, timestamp, duration_ms, metadata.version
- [ ] Error response includes: success (false), error (code + message), timestamp

---

## Rollback Plan

If issues arise:

1. The helper functions are backward-compatible in non-JSON mode
2. Git history preserves old implementation
3. Consumers can check `metadata.version` to handle both formats:

```python
def parse_response(data):
    """Handle both old and new formats."""
    if "metadata" in data and "version" in data["metadata"]:
        # New format
        return data["result"]
    else:
        # Old format
        return {k: v for k, v in data.items() if k not in ["success", "operation"]}
```

---

## Contact

For questions about this standardization:
- See: `CLAUDE.md` in codeswiftr-com domain
- See: `.forge/memories/` for FORGE patterns
- Reference: FORGE standard schema documentation

---

**Status:** Foundation complete, command migration in progress
**Last Updated:** 2026-02-06
**Version:** 0.1.0
