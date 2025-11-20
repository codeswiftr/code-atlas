# Code Atlas Deployment Guide

This guide provides a comprehensive checklist and procedures for deploying Code Atlas MVP to production.

## Pre-Deployment Checklist

### Prerequisites
- [ ] **Python 3.11+** installed and verified
- [ ] **Docker** and **Docker Compose** installed and running
- [ ] **uv** package manager installed (or pip as fallback)
- [ ] **Anthropic API key** obtained (optional, for LLM extraction)
- [ ] **FalkorDB** accessible (via Docker or external service)
- [ ] **Disk space** available (minimum 10GB recommended)
- [ ] **Network access** to Anthropic API (if using LLM extraction)
- [ ] **Read access** to Claude session files directory

### Code Quality Validation
- [x] All linting errors fixed
- [x] All unit tests passing (82% coverage achieved)
- [x] Integration tests verified (skip gracefully when services unavailable)
- [x] Code review completed
- [x] Documentation updated and accurate

### Configuration Review
- [x] `.code-atlas.toml` configuration file created or reviewed
- [x] Environment variables documented (`.env.example` provided)
- [ ] API keys securely stored (not committed to repository)
- [ ] Cost limits configured appropriately
- [ ] Session directories paths verified

## Installation Steps

### 1. Clone Repository
```bash
# Replace <repository-url> with actual repository URL
git clone <repository-url>
cd code-atlas/backend
```

**Note**: Update `<repository-url>` with the actual repository URL before beta launch.

### 2. Install Dependencies
```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 3. Configure Environment
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Required: ANTHROPIC_API_KEY (if using LLM extraction)
# Optional: Override defaults (see .env.example)
```

### 4. Create Configuration File (Optional)
```bash
# Create .code-atlas.toml in project root
cat > .code-atlas.toml <<EOF
[discovery]
claude_root = "~/.claude/projects"
max_session_size_mb = 50

[extraction]
use_llm = true
model = "claude-3-5-sonnet-latest"
max_cost_per_session_usd = 0.02

[graph]
graph_name = "code_atlas"
redis_url = "redis://localhost:6379"

[pipeline]
max_retries = 3
max_cumulative_cost_usd = 10.0
EOF
```

### 5. Start Services
```bash
# Start FalkorDB via Docker Compose
docker compose up -d

# Verify services are running
docker compose ps
```

## Configuration Verification

### Verify Service Health
```bash
# Check FalkorDB is accessible
redis-cli -h localhost -p 6379 PING
# Should return: PONG

# Verify FalkorDB supports GRAPH commands
redis-cli -h localhost -p 6379 GRAPH.QUERY test "RETURN 1"
# Should execute successfully (or error gracefully if not FalkorDB)
```

### Verify Configuration Loading
```bash
# Test configuration loading
uv run code-atlas discover --limit 1
# Should list sessions or show "No sessions" message

# Test with explicit config
uv run code-atlas discover --config .code-atlas.toml --limit 1
```

### Verify API Access (if using LLM)
```bash
# Test API key is set
echo $ANTHROPIC_API_KEY | head -c 10

# Test API access with dry run
uv run code-atlas run --dry-run --use-llm --limit 1
# Should execute without API errors (or fall back gracefully)
```

## Service Startup Verification

### Check Docker Services
```bash
# Verify FalkorDB container is running
docker ps | grep falkordb

# Check container logs for errors
docker compose logs falkordb | tail -50

# Verify port binding
netstat -an | grep 6379
# Should show LISTEN on 6379
```

### Verify Python Environment
```bash
# Verify CLI is accessible
uv run code-atlas --help

# Verify imports work
python -c "import code_atlas; print('OK')"

# Verify dependencies installed
uv run python -c "import anthropic, redis, structlog; print('OK')"
```

## Smoke Tests

### Test 1: Discovery
```bash
# Should discover sessions without errors
uv run code-atlas discover --limit 5

# Expected: Table with session IDs, projects, modified dates, sizes
# Or: "No sessions" message if none found
```

### Test 2: Dry Run
```bash
# Should process sessions without database writes
uv run code-atlas run --dry-run --limit 3

# Expected: Pipeline summary table with stats
# Should show: Sessions, Messages, Tokens, Entities, etc.
# No errors in output
```

### Test 3: Heuristic Mode
```bash
# Should process with heuristics (no API calls)
uv run code-atlas run --no-dry-run --no-use-llm --limit 3

# Expected: Sessions processed, entities created
# Cost should be $0.00 (heuristics are free)
# Check FalkorDB for nodes created
```

### Test 4: LLM Mode (Optional)
```bash
# Should process with LLM extraction
uv run code-atlas run --no-dry-run --use-llm --limit 1

# Expected: Sessions processed with cost > $0
# Check cost is within limits (< $0.02/session)
# Verify entities and relationships in graph
```

### Test 5: Report Generation
```bash
# Should generate report from graph
uv run code-atlas report --top-n 10

# Expected: Tables showing top files, concepts, session statistics
# Or: "Graph appears to be empty" if no data
```

### Test 6: Structured Logging
```bash
# Should produce JSON structured logs
export CODE_ATLAS_LOG_LEVEL=DEBUG
uv run code-atlas run --dry-run --limit 1 2>&1 | head -1 | jq .

# Expected: Valid JSON with keys: event, level, logger, timestamp, etc.
```

## Post-Deployment Validation

### Verify Data in FalkorDB
```bash
# Connect to FalkorDB
redis-cli -h localhost -p 6379

# Count sessions
GRAPH.QUERY code_atlas "MATCH (s:Session) RETURN count(s)"

# Count entities
GRAPH.QUERY code_atlas "MATCH (e) WHERE NOT e:Session RETURN count(e)"

# Count relationships
GRAPH.QUERY code_atlas "MATCH ()-[r]->() RETURN count(r)"

# Verify provenance metadata
GRAPH.QUERY code_atlas "MATCH (s:Session) RETURN s.extraction_method, s.extractor_model LIMIT 5"
```

### Verify Error Handling
```bash
# Test with invalid session (should quarantine)
# Test with cost limit exceeded (should fall back)
# Test with network errors (should retry)
```

### Verify Performance
```bash
# Process batch and measure time
time uv run code-atlas run --no-dry-run --no-use-llm --limit 100

# Expected: ~100 sessions/minute for heuristics
# Expected: ~10-20 sessions/minute for LLM mode
```

## Monitoring Setup

### Enable Structured Logging
```bash
# Set log level via environment
export CODE_ATLAS_LOG_LEVEL=INFO  # or DEBUG for verbose

# Logs are JSON formatted and can be piped to logging service
uv run code-atlas run --limit 100 > logs/pipeline.log 2>&1
```

### Monitor Costs
```bash
# Track cumulative costs in logs
grep "cumulative_cost_usd" logs/pipeline.log

# Track per-session costs
grep "cost_usd" logs/pipeline.log | jq .
```

### Monitor Errors
```bash
# Track errors in logs
grep "level.*error" logs/pipeline.log | jq .

# Track quarantined sessions
ls -la .code-atlas-quarantine/
```

### Monitor Graph Growth
```bash
# Track graph size
redis-cli INFO memory | grep used_memory_human

# Track node counts
redis-cli GRAPH.QUERY code_atlas "MATCH (n) RETURN count(n)"
```

## Rollback Procedures

### If Deployment Fails

#### Rollback Code
```bash
# Revert to previous version
git checkout <previous-tag-or-commit>
uv sync
```

#### Rollback Data
```bash
# Restore FalkorDB from backup (if available)
docker compose down
# Restore backup (see RUNBOOK.md Backup & Recovery section)
docker compose up -d
```

#### Rollback Configuration
```bash
# Restore previous config
cp .code-atlas.toml.backup .code-atlas.toml

# Or revert environment variables
cp .env.backup .env
```

### If Services Fail

#### Restart FalkorDB
```bash
# Stop and restart
docker compose restart falkordb

# Or full restart
docker compose down
docker compose up -d

# Verify health
redis-cli PING
```

#### Clear Problematic Data (Last Resort)
```bash
# Delete graph (careful - permanent!)
redis-cli GRAPH.DELETE code_atlas

# Re-run pipeline to repopulate
uv run code-atlas run --no-dry-run --limit 1000
```

## Production Recommendations

### Security
- [ ] Store API keys in secure secret management system
- [ ] Bind FalkorDB to localhost only (not 0.0.0.0)
- [ ] Enable firewall rules to restrict access
- [ ] Use authentication for FalkorDB in production
- [ ] Review session data for PII before processing

### Performance
- [ ] Process in batches during off-peak hours
- [ ] Monitor disk space for graph growth
- [ ] Set up automated backups for FalkorDB
- [ ] Consider read replicas for query performance

### Monitoring
- [ ] Set up log aggregation (ELK, Loki, etc.)
- [ ] Set up cost alerts (if using LLM)
- [ ] Monitor error rates and quarantined sessions
- [ ] Track graph growth and plan for scaling

### Backup
- [ ] Schedule daily FalkorDB backups
- [ ] Store backups off-site
- [ ] Test backup restoration procedures
- [ ] Document backup retention policies

## Troubleshooting

See [RUNBOOK.md](RUNBOOK.md) for detailed troubleshooting procedures.

Common issues:
- **FalkorDB connection errors**: Check docker compose status
- **Cost limit exceeded**: Increase limits or use heuristics
- **No sessions discovered**: Verify claude_root path
- **Memory errors**: Reduce batch size or max_session_size_mb

## Support

For deployment issues:
1. Check [RUNBOOK.md](RUNBOOK.md) troubleshooting section
2. Review logs: `logs/pipeline.log`
3. Enable debug logging: `export CODE_ATLAS_LOG_LEVEL=DEBUG`
4. Create minimal reproduction case
5. Open GitHub issue with logs and reproduction steps

## Beta Launch Specific Steps

### Pre-Beta Launch Checklist (1 Week Before)

- [ ] **End-to-End Validation**: Run complete deployment in clean environment
  ```bash
  # Test in clean Docker environment
  docker compose down -v
  docker compose up -d
  # Follow Installation Steps above
  # Run all Smoke Tests
  ```

- [ ] **Beta User Onboarding Preparation**
  - [ ] Beta user documentation ready (see [BETA-SUMMARY.md](BETA-SUMMARY.md))
  - [ ] Beta feedback collection process established
  - [ ] Beta user access credentials prepared

- [ ] **Monitoring Setup**
  - [ ] Log aggregation configured (if applicable)
  - [ ] Cost monitoring alerts configured
  - [ ] Error tracking dashboard ready
  - [ ] Daily health check procedures documented

- [ ] **Beta Scope Verification**
  - [ ] Verify beta feature set matches [BETA-SUMMARY.md](BETA-SUMMARY.md)
  - [ ] Known limitations documented
  - [ ] Beta user expectations set appropriately

### Beta Launch Day Checklist

- [ ] **Pre-Launch Verification** (morning)
  - [ ] All services running and healthy
  - [ ] Smoke tests passing
  - [ ] Configuration validated
  - [ ] Backup procedures tested

- [ ] **Beta User Onboarding** (day of launch)
  - [ ] Beta users notified and onboarded
  - [ ] Quick start guide provided
  - [ ] Support channels established
  - [ ] Feedback collection process activated

- [ ] **Post-Launch Monitoring** (first 24 hours)
  - [ ] Monitor error rates hourly
  - [ ] Track cost usage
  - [ ] Monitor graph growth
  - [ ] Collect initial feedback

### Beta Launch First Week Monitoring

- [ ] **Daily Checks**
  - [ ] Service health and uptime
  - [ ] Error rates and quarantined sessions
  - [ ] Cost usage vs limits
  - [ ] Graph growth and performance
  - [ ] User feedback review

- [ ] **Weekly Review** (end of first week)
  - [ ] Stability assessment
  - [ ] Performance metrics review
  - [ ] Cost analysis
  - [ ] User feedback compilation
  - [ ] Known issues prioritization

### Beta Feedback Collection

**Feedback Channels**:
- GitHub Issues (preferred)
- Email: [beta-feedback@codeswiftr.com] (update with actual email)
- Internal Slack channel: [code-atlas-beta] (if applicable)

**Feedback Template**:
```
## Beta Feedback

**Date**: [Date]
**User**: [Name/Email]
**Feature/Issue**: [Brief description]

### Details
[Detailed description]

### Expected Behavior
[What you expected]

### Actual Behavior
[What actually happened]

### Steps to Reproduce
[If applicable]

### Environment
- OS: [e.g., macOS 14.1]
- Python: [e.g., 3.11.5]
- Code Atlas version: [e.g., beta-2025-01-17]

### Additional Context
[Any other relevant information]
```

## Next Steps

After successful beta deployment:
1. Monitor initial runs for stability
2. Review cost usage and adjust limits
3. Process initial batch of sessions
4. Verify graph queries return expected results
5. Collect and review beta feedback weekly
6. Prioritize bug fixes and feature requests
7. Plan Phase 2 features based on feedback
8. Document production-specific procedures

