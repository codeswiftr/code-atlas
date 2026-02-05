# Code Atlas CLI Tests

Comprehensive test suite for the Code Atlas CLI (`code-atlas` command).

## Test Files

| File | Purpose | Test Count | Status |
|------|---------|------------|--------|
| `test_cli.py` | Full CLI test suite with mocking | 30+ tests | Complete implementation |
| `test_cli_complete.py` | Documented test template | 4+ tests | Template/Reference |
| `test_cli_simple.py` | Subprocess-based CLI tests | 11 tests | Implementation complete |

## Commands Tested

All 10 CLI commands are covered:

1. **discover** - List discovered Claude sessions
2. **index** - Index sessions into knowledge graph
3. **run** - Legacy alias for index
4. **query** - Query knowledge graph with natural language
5. **export** - Export graph data (JSON/Cypher/GraphML)
6. **status** - Show graph statistics
7. **report** - Generate summary report
8. **indexes** - Manage database indexes
9. **metrics** - Start Prometheus metrics server
10. **serve** - Start FastAPI API server

## Test Coverage

### Success Scenarios
- Normal (Rich) output mode
- JSON output mode (`--json` flag)
- Command-specific options and filters
- Dry-run modes where applicable

### Error Scenarios
- Connection failures (Redis/FalkorDB unavailable)
- Invalid arguments (format, provider, action)
- Missing resources (root directory not found)
- Configuration errors

### Edge Cases
- Empty results
- Zero-session processing
- Disabled features (metrics)

## Running Tests

### Quick Start

```bash
# Install dependencies
cd backend
uv sync

# Run all CLI tests
uv run pytest tests/test_cli.py -v

# Run with coverage
uv run pytest tests/test_cli.py --cov=code_atlas.cli --cov-report=html

# Run specific command tests
uv run pytest tests/test_cli.py -k discover -v
```

### Environment Setup

**CRITICAL: OpenMP Library Conflict**

The CLI imports `sentence-transformers` (via `hybrid_search.py → embeddings.py`) which can cause OpenMP library conflicts on macOS. This manifests as hanging on import or the error:

```
OMP: Error #15: Initializing libomp.dylib, but found libomp.dylib already initialized
```

**Solution:**

```bash
export KMP_DUPLICATE_LIB_OK=TRUE
uv run pytest tests/test_cli.py -v
```

This environment variable is set automatically in the test files, but may need to be set manually for some test runners.

### Integration Tests

Some tests require external services:

```bash
# Start FalkorDB
docker-compose up -d

# Run integration tests only
uv run pytest tests/test_cli.py -m integration -v

# Skip integration tests
uv run pytest tests/test_cli.py -m "not integration" -v
```

## Test Architecture

### Mocking Strategy

Tests use comprehensive mocking to avoid external dependencies:

```python
@patch("code_atlas.cli.load_settings")
@patch("code_atlas.cli.SessionDiscovery")
@patch("code_atlas.cli.InsightExtractor")
@patch("code_atlas.cli.GraphPopulator")
@patch("code_atlas.cli.PipelineRunner")
def test_index_sessions_json_output(...):
    # Setup mocks
    mock_runner.run.return_value = PipelineStats(...)

    # Invoke CLI
    result = runner.invoke(app, ["index", "--json"])

    # Verify output
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success"] is True
```

### Test Fixtures

Reusable fixtures for common test data:

- `mock_settings` - Test AtlasSettings configuration
- `sample_session_metadata` - Sample session metadata
- `sample_extraction` - Sample extraction result
- `sample_pipeline_stats` - Sample pipeline statistics

### JSON Output Validation

All commands with `--json` flag have tests validating:

```python
# Success response
{
    "success": true,
    "operation": "command-name",
    ...command-specific-data
}

# Error response
{
    "success": false,
    "operation": "command-name",
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable message",
        "details": {}
    }
}
```

## Known Issues

### Import Hanging

**Symptom:** Tests hang during import or collection phase.

**Root Cause:** `sentence-transformers` library has OpenMP library conflicts on macOS.

**Workaround:**
```bash
export KMP_DUPLICATE_LIB_OK=TRUE
```

**Long-term Fix:** Lazy-load sentence-transformers models in `embeddings.py` instead of eager initialization.

### Subprocess Timeouts

**Symptom:** `test_cli_simple.py` tests timeout when running CLI via subprocess.

**Root Cause:** Same OpenMP conflict affects subprocesses.

**Workaround:** Environment variable is passed to subprocess:
```python
env = os.environ.copy()
env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
subprocess.run(..., env=env)
```

### Metrics Server Tests

**Symptom:** Metrics server tests may not fully start the server.

**Explanation:** FastAPI server startup is asynchronous and difficult to test without full integration.

**Solution:** Basic tests verify initial output and error handling. Full server functionality tested in `test_server.py`.

## Test Quality Standards

### Coverage Requirements
- Minimum 80% line coverage for `cli.py`
- All commands must have both success and error tests
- JSON output must be validated for all commands

### Test Naming
- `test_<command>_<scenario>` pattern
- Clear, descriptive names
- Group related tests in classes

### Documentation
- Docstrings for all test functions
- Comments for complex mock setups
- README updates for new test files

## Continuous Integration

### GitHub Actions

```yaml
- name: Test CLI
  env:
    KMP_DUPLICATE_LIB_OK: "TRUE"
  run: |
    uv run pytest tests/test_cli.py -v --cov=code_atlas.cli
```

### Pre-commit Hooks

```bash
# Run CLI tests before commit
uv run pytest tests/test_cli.py -q
```

## Troubleshooting

### Tests hang on import

1. Check OpenMP environment variable:
   ```bash
   echo $KMP_DUPLICATE_LIB_OK  # Should output: TRUE
   ```

2. Verify sentence-transformers installation:
   ```bash
   uv pip list | grep sentence
   ```

3. Try disabling sentence-transformers temporarily:
   ```bash
   uv pip uninstall sentence-transformers
   uv run pytest tests/test_cli.py -v
   ```

### Mock not working

1. Ensure full patch path: `@patch("code_atlas.cli.Module")`
2. Check mock is passed to test function in correct order
3. Verify return values are set before invocation

### JSON parse errors

1. Check stdout contains valid JSON:
   ```python
   print(result.stdout)  # Add for debugging
   ```

2. Verify no extra output (warnings, logs) before JSON
3. Use `mix_stderr=False` in CliRunner

## Future Improvements

### High Priority
- [ ] Add tests for `--config` file loading
- [ ] Test all export formats (JSON, Cypher, GraphML)
- [ ] Test metrics server lifecycle
- [ ] Test WebSocket connections in serve command

### Medium Priority
- [ ] Parameterize tests for better coverage
- [ ] Add performance benchmarks
- [ ] Test error message formatting
- [ ] Test signal handling (SIGINT, SIGTERM)

### Low Priority
- [ ] Test color output in Rich tables
- [ ] Test progress bars and spinners
- [ ] Test interactive prompts (indexes drop confirmation)
- [ ] Cross-platform testing (Windows, Linux)

## References

- [Typer Testing Documentation](https://typer.tiangolo.com/tutorial/testing/)
- [pytest Mocking Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)
- [Code Atlas CLI Source](/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/backend/src/code_atlas/cli.py)

## Contributing

When adding new CLI commands:

1. Add tests to `test_cli.py`
2. Test both normal and JSON output
3. Add error scenario tests
4. Update this README
5. Run full test suite before PR

## Questions?

See the main project documentation or reach out to the team.
