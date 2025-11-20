# Code Atlas Beta Launch Summary

This document provides an executive summary of the Code Atlas MVP beta launch, including scope, limitations, and quick start guide for beta testers.

## Beta Launch Overview

**Launch Date**: 2025-01-17 (target)  
**Duration**: 2 weeks (minimum)  
**Status**: Preparation in Progress

### What is Code Atlas?

Code Atlas is an automated pipeline that ingests Claude Code session logs, extracts structured knowledge (entities, relationships, insights), and stores them in a searchable knowledge graph (FalkorDB). It enables teams to search and analyze all AI-assisted coding sessions, discover patterns, and build institutional memory.

## Beta Scope

### What's Included in Beta

✅ **Complete MVP Features**:
1. **Session Discovery**: Automatically scans `~/.claude/projects` for session files
2. **Session Parsing**: Streaming JSONL parser with typed models
3. **Insight Extraction**: 
   - LLM-powered extraction (Claude API)
   - Heuristic fallback (no API costs)
   - Automatic chunking for large sessions
4. **Knowledge Graph**: FalkorDB integration with provenance metadata
5. **Retry Logic**: Exponential backoff with error quarantine
6. **Cost Guards**: Enforces spending limits ($0.02/session default)
7. **CLI Commands**: 
   - `discover` - List discovered sessions
   - `run` - Process sessions and populate graph
   - `report` - Generate knowledge graph reports
8. **Configuration**: TOML file and environment variable support
9. **Structured Logging**: JSON logs with contextual metadata

✅ **Documentation**:
- Complete user guide (README.md)
- Operations runbook (RUNBOOK.md)
- Deployment procedures (DEPLOYMENT.md)
- Beta launch checklist (BETA-LAUNCH.md)

✅ **Testing**:
- 82% test coverage
- Unit and integration tests
- End-to-end pipeline tests

### What's NOT Included in Beta

❌ **Phase 2 Features** (Planned for post-beta):
- Incremental ingest via file watcher
- Advanced redaction and compliance checks
- Prometheus metrics and Grafana dashboards
- Batch scheduling (cron/GitHub Actions)

❌ **Phase 3 Features** (Future):
- FastAPI query service
- Web console/UI
- GraphRAG assistant
- Slack/MCP integration

## Known Limitations

### Beta Limitations

1. **CLI-Only Interface**
   - No web UI or API endpoints
   - All operations via command line
   - Reports are console-based (tables)

2. **Manual Processing**
   - No automatic file watching
   - No scheduled batch processing
   - Must run pipeline manually or via cron

3. **Basic Monitoring**
   - Structured logging only (no dashboards)
   - No Prometheus metrics
   - Manual cost tracking via logs

4. **Limited Redaction**
   - Basic filtering available
   - No automatic PII detection
   - No advanced compliance features

5. **Single Instance**
   - No multi-tenant support
   - No distributed processing
   - Local FalkorDB instance only

6. **No Graph Embeddings**
   - No semantic search
   - Cypher queries only
   - No vector similarity search

### Workarounds

- **Manual Scheduling**: Use cron or GitHub Actions to schedule runs
- **Monitoring**: Review structured logs (JSON format) manually
- **Redaction**: Use `.code-atlas-ignore` file to exclude sensitive sessions
- **Multi-User**: Each user runs their own instance (shared FalkorDB possible)

## Beta Success Criteria

### Technical Metrics

- Process 50 sessions/day with <1% error rate
- Cost per session <$0.02 (when using LLM)
- End-to-end pipeline processing time <1 minute per session
- Graph query latency <150ms for common queries

### User Experience Metrics

- Beta users can successfully onboard (100% success rate)
- Beta users can complete basic workflows without blockers
- At least 3 actionable feedback items collected
- No critical bugs blocking usage

## Quick Start Guide for Beta Testers

### Prerequisites

- Python 3.11+ installed
- Docker and Docker Compose installed
- Anthropic API key (optional, for LLM extraction)
- Claude Code sessions available in `~/.claude/projects`

### Installation (5 minutes)

```bash
# 1. Clone repository
git clone <repository-url>
cd code-atlas/backend

# 2. Install dependencies
uv sync
# Or: pip install -e .

# 3. Configure environment
cp .env.example .env
# Edit .env with your API key (optional)

# 4. Start services
docker compose up -d

# 5. Verify installation
uv run code-atlas discover --limit 5
```

### First Run (10 minutes)

```bash
# 1. Discover sessions
uv run code-atlas discover --limit 10

# 2. Dry run (preview without database writes)
uv run code-atlas run --dry-run --limit 3

# 3. Run with heuristics (fast, no API costs)
uv run code-atlas run --no-dry-run --no-use-llm --limit 10

# 4. Run with LLM extraction (higher quality, costs ~$0.02/session)
uv run code-atlas run --no-dry-run --use-llm --limit 5

# 5. Generate report
uv run code-atlas report --top-n 20
```

### Common Workflows

**Process All Recent Sessions**:
```bash
uv run code-atlas run --no-dry-run --use-llm --limit 100
```

**Process Specific Project**:
```bash
uv run code-atlas discover --include-project my-project --limit 10
uv run code-atlas run --no-dry-run --use-llm --limit 10
```

**Query Graph Directly**:
```bash
redis-cli -h localhost -p 6379 GRAPH.QUERY code_atlas "MATCH (f:File) RETURN f.name LIMIT 10"
```

**View Quarantined Sessions**:
```bash
ls -la .code-atlas-quarantine/
```

### Troubleshooting

**FalkorDB Not Running**:
```bash
docker compose up -d
docker compose ps
```

**No Sessions Discovered**:
```bash
# Verify Claude root path
ls -la ~/.claude/projects
# Override path if needed
uv run code-atlas discover --root /path/to/projects --limit 5
```

**Cost Limit Exceeded**:
```bash
# Use heuristics instead of LLM
uv run code-atlas run --no-dry-run --no-use-llm --limit 100

# Or increase limits in .env
CODE_ATLAS_MAX_CUMULATIVE_COST=20.0
```

See [RUNBOOK.md](RUNBOOK.md) for detailed troubleshooting.

## Beta Feedback

### How to Provide Feedback

1. **GitHub Issues** (Preferred)
   - Create issue with label: `beta-feedback`
   - Use feedback template from [BETA-LAUNCH.md](BETA-LAUNCH.md)

2. **Email**
   - Send to: [beta-feedback@codeswiftr.com] (update with actual email)
   - Subject: `[Code Atlas Beta] <Brief description>`

### What to Report

✅ **Please Report**:
- Bugs or errors
- Performance issues
- Missing features
- Documentation gaps
- Usability issues
- Feature requests

❌ **Please Don't Report**:
- Known limitations (listed above)
- Phase 2/3 features (not in scope)
- General questions (use documentation first)

### Feedback Priority

- **Critical**: System crashes, data loss, security issues
- **High**: Major bugs, performance issues
- **Medium**: Minor bugs, feature improvements
- **Low**: Nice-to-have features, future enhancements

## Beta Timeline

### Week 1: Initial Testing

- **Day 1-2**: Installation and first runs
- **Day 3-4**: Processing initial batch of sessions
- **Day 5-7**: Testing various workflows, collecting initial feedback

### Week 2: Deep Testing

- **Day 8-10**: Extended testing, performance evaluation
- **Day 11-12**: Feedback review and prioritization
- **Day 13-14**: Beta review meeting, planning next steps

### Post-Beta

- **Week 3**: Fix critical bugs based on feedback
- **Week 4**: Prioritize Phase 2 features
- **Month 2**: Plan production launch (if beta successful)

## Resources

### Documentation

- **[README.md](../README.md)** - Complete user guide and reference
- **[RUNBOOK.md](RUNBOOK.md)** - Operations guide and troubleshooting
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment procedures
- **[BETA-LAUNCH.md](BETA-LAUNCH.md)** - Beta launch checklist

### Support

- **Technical Issues**: [GitHub Issues](https://github.com/codeswiftr-com/code-atlas/issues)
- **General Questions**: [beta-support@codeswiftr.com] (update with actual email)
- **Urgent Issues**: [Slack channel or contact info] (if applicable)

### Response Times

- **Critical Issues**: Within 4 hours
- **High Priority**: Within 24 hours
- **Medium Priority**: Within 3 days
- **Low Priority**: Within 1 week

## Next Steps

1. **Complete Installation**: Follow Quick Start Guide above
2. **Process First Sessions**: Run pipeline on your Claude sessions
3. **Explore Graph**: Generate reports and query the knowledge graph
4. **Provide Feedback**: Share your experience and suggestions
5. **Stay Updated**: Watch repository for updates and fixes

Thank you for participating in the Code Atlas beta launch!

