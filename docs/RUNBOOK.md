# Code Atlas Operations Runbook

This guide provides operational procedures for running, monitoring, and troubleshooting Code Atlas in production environments.

## System Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4GB | 8GB |
| Disk Space | 10GB | 50GB+ |
| Network | 1 Mbps | 10 Mbps |

**Disk Usage Breakdown:**
- Claude session files: ~1-5GB (typical)
- FalkorDB graph data: ~500MB-2GB
- Docker images: ~2GB
- Python dependencies: ~500MB

### Software

- **Docker**: 20.10+ with Docker Compose
- **Python**: 3.11+ (for tomllib support)
- **uv**: Latest (or pip as fallback)
- **Redis/FalkorDB**: via Docker (included)

## Deployment

### Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/codeswiftr-com/code-atlas.git
cd code-atlas/backend

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings

# 4. Start services
docker compose up -d

# 5. Verify installation
uv run code-atlas discover --limit 5
```

### Production Deployment

#### Docker Compose Configuration

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  falkordb:
    image: falkordb/falkordb:latest
    container_name: code-atlas-falkordb
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - falkordb_data:/data
    environment:
      - REDIS_ARGS=--save 60 1 --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  falkordb_data:
    driver: local
```

#### Production Environment Variables

```bash
# .env.production
CODE_ATLAS_CLAUDE_ROOT=/data/claude/projects
CODE_ATLAS_MAX_SESSION_MB=100
CODE_ATLAS_MAX_COST_PER_SESSION=0.05
CODE_ATLAS_MAX_CUMULATIVE_COST=50.0
ANTHROPIC_API_KEY=sk-ant-your-production-key
```

#### Security Considerations

1. **API Keys**: Store in environment variables, never commit to git
2. **Network**: Bind FalkorDB to localhost only in production
3. **Backups**: Schedule daily backups (see Backup & Recovery section)
4. **Access Control**: Use firewall rules to restrict access
5. **Monitoring**: Enable logging and alerting

## Configuration Reference

### Complete Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `claude_root` | Path | `~/.claude/projects` | Root directory for Claude sessions |
| `ignore_file` | Path | `None` | Gitignore-style file for exclusions |
| `max_session_size_mb` | int | `50` | Skip sessions larger than this (MB) |
| `use_llm` | bool | `false` | Use Claude API vs heuristics |
| `model` | str | `claude-3-5-sonnet-latest` | Claude model for extraction |
| `max_tokens` | int | `1024` | Max tokens for extraction responses |
| `temperature` | float | `0` | LLM temperature (0 = deterministic) |
| `max_cost_per_session_usd` | float | `0.02` | Cost limit per session |
| `graph_name` | str | `code_atlas` | FalkorDB graph name |
| `redis_url` | str | `redis://localhost:6379` | FalkorDB connection URL |
| `max_retries` | int | `3` | Retry attempts for failures |
| `retry_delay_base` | float | `1.0` | Base delay for exponential backoff |
| `quarantine_dir` | Path | `.code-atlas-quarantine` | Failed session storage |
| `max_cumulative_cost_usd` | float | `10.0` | Total cost limit per run |

### Environment Variables

All settings can be set via environment variables with `CODE_ATLAS_` prefix:

```bash
# Discovery
export CODE_ATLAS_CLAUDE_ROOT=~/my-projects
export CODE_ATLAS_IGNORE_FILE=.atlas-ignore
export CODE_ATLAS_MAX_SESSION_MB=75

# Extraction
export CODE_ATLAS_MAX_COST_PER_SESSION=0.03
export CODE_ATLAS_MAX_CUMULATIVE_COST=20.0

# Graph
export CODE_ATLAS_REDIS_URL=redis://prod-redis:6379

# API Key
export ANTHROPIC_API_KEY=sk-ant-...
```

### Configuration Priority

Settings are loaded in this order (later overrides earlier):

1. Default values (hardcoded)
2. `.code-atlas.toml` file
3. Environment variables
4. CLI flags

## Common Operations

### Running the Pipeline

#### Standard Run

```bash
# Process up to 100 sessions with LLM extraction
uv run code-atlas run --no-dry-run --use-llm --limit 100
```

#### With Custom Configuration

```bash
# Use production config
uv run code-atlas run --config /etc/code-atlas/prod.toml --limit 500
```

#### Dry Run for Testing

```bash
# Preview without database writes or API calls
uv run code-atlas run --dry-run --limit 5
```

#### Batch Processing

```bash
# Process in smaller batches to control costs
for i in {1..10}; do
  uv run code-atlas run --no-dry-run --use-llm --limit 50
  sleep 60  # Rate limiting
done
```

#### Heuristic-Only Mode (No API Costs)

```bash
# Fast processing without LLM calls
uv run code-atlas run --no-dry-run --no-use-llm --limit 1000
```

### Querying the Graph

#### Via CLI Report

```bash
# Standard report
uv run code-atlas report

# Top 50 entities
uv run code-atlas report --top-n 50

# Custom graph name
uv run code-atlas report --graph-name my_atlas
```

#### Direct Cypher Queries

```bash
# Find all files
redis-cli GRAPH.QUERY code_atlas "MATCH (f:File) RETURN f.name LIMIT 10"

# Find relationships between entities
redis-cli GRAPH.QUERY code_atlas "
MATCH (a)-[r]->(b)
RETURN a.name, type(r), b.name
LIMIT 20
"

# Find most connected sessions
redis-cli GRAPH.QUERY code_atlas "
MATCH (s:Session)-[r]->()
RETURN s.project, s.id, COUNT(r) AS connections
ORDER BY connections DESC
LIMIT 10
"
```

#### Python API

```python
import redis

client = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)

# Execute query
result = client.execute_command(
    "GRAPH.QUERY",
    "code_atlas",
    "MATCH (f:File)<-[:MENTIONS]-(s:Session) RETURN f.name, COUNT(s)",
    "--compact"
)

# Result format: [headers, rows, stats]
headers = result[0]
rows = result[1]
for row in rows:
    print(f"File: {row[0]}, Sessions: {row[1]}")
```

## Troubleshooting

### Pipeline Fails to Connect to FalkorDB

**Symptom**: `ConnectionError: Could not connect to redis://localhost:6379`

**Diagnosis**:
```bash
# Check if FalkorDB container is running
docker ps | grep falkordb

# Check container logs
docker compose logs falkordb

# Test connection
nc -zv localhost 6379
```

**Solutions**:

1. **Start services**:
   ```bash
   docker compose up -d
   docker compose ps  # Verify running
   ```

2. **Check port binding**:
   ```bash
   netstat -an | grep 6379
   # Should show LISTEN on 6379
   ```

3. **Verify Docker network**:
   ```bash
   docker network inspect code-atlas_default
   ```

4. **Check firewall**:
   ```bash
   # macOS
   sudo pfctl -s rules | grep 6379

   # Linux
   sudo iptables -L -n | grep 6379
   ```

### Cost Limit Exceeded

**Symptom**: `CostLimitExceeded: Cumulative cost $10.50 exceeds limit $10.00`

**Diagnosis**:
```bash
# Check cumulative spend in logs
grep "cumulative cost" logs/pipeline.log

# Estimate session costs
uv run code-atlas discover --limit 100 | grep "Size (KB)"
```

**Solutions**:

1. **Increase limit in config**:
   ```toml
   [pipeline]
   max_cumulative_cost_usd = 20.0
   ```

2. **Process in smaller batches**:
   ```bash
   uv run code-atlas run --limit 50
   # Check cost, then run again
   uv run code-atlas run --limit 50
   ```

3. **Use heuristics instead of LLM**:
   ```bash
   uv run code-atlas run --no-use-llm --limit 500
   ```

4. **Filter by project**:
   ```bash
   uv run code-atlas run --include-project important-proj --use-llm
   ```

### Sessions Not Discovered

**Symptom**: `No sessions processed. Check filters/root path.`

**Diagnosis**:
```bash
# Verify Claude root exists
ls -la ~/.claude/projects

# Check for .jsonl files
find ~/.claude/projects -name "*.jsonl" -type f

# Test discovery
uv run code-atlas discover --limit 10
```

**Solutions**:

1. **Verify path**:
   ```bash
   # Override root path
   uv run code-atlas discover --root ~/.claude/sessions
   ```

2. **Check permissions**:
   ```bash
   # Ensure read permissions
   chmod -R u+r ~/.claude/projects
   ```

3. **Verify file format**:
   ```bash
   # Check if files are valid JSONL
   head -n 1 ~/.claude/projects/my-project/session.jsonl | jq .
   ```

4. **Check ignore file**:
   ```bash
   # Temporarily disable ignore file
   mv .code-atlas-ignore .code-atlas-ignore.bak
   uv run code-atlas discover
   ```

### Memory Errors During Processing

**Symptom**: `MemoryError` or container OOM killed

**Diagnosis**:
```bash
# Check session sizes
find ~/.claude/projects -name "*.jsonl" -exec du -h {} \; | sort -hr | head

# Monitor memory usage
docker stats code-atlas-falkordb
```

**Solutions**:

1. **Reduce session size limit**:
   ```toml
   [discovery]
   max_session_size_mb = 25  # Reduce from 50
   ```

2. **Increase Docker memory**:
   ```bash
   # In Docker Desktop: Settings > Resources > Memory
   # Or in daemon.json:
   {
     "default-ulimits": {
       "memlock": {
         "hard": 8589934592,
         "soft": 8589934592
       }
     }
   }
   ```

3. **Process smaller batches**:
   ```bash
   uv run code-atlas run --limit 10
   ```

### Extraction Quality Issues

**Symptom**: Poor entity extraction or missing relationships

**Diagnosis**:
```bash
# Compare LLM vs heuristics
uv run code-atlas run --dry-run --use-llm --limit 1 > llm.log
uv run code-atlas run --dry-run --no-use-llm --limit 1 > heuristic.log
diff llm.log heuristic.log
```

**Solutions**:

1. **Use LLM extraction**:
   ```bash
   uv run code-atlas run --use-llm --limit 100
   ```

2. **Increase max_tokens**:
   ```toml
   [extraction]
   max_tokens = 2048  # Increase from 1024
   ```

3. **Use newer model**:
   ```toml
   [extraction]
   model = "claude-3-5-sonnet-latest"
   ```

4. **Check session quality**:
   ```bash
   # Review sample session
   cat ~/.claude/projects/my-project/session.jsonl | jq '.' | head -100
   ```

## Monitoring

### Health Checks

```bash
# Check all services
docker compose ps

# Verify FalkorDB
redis-cli PING  # Should return PONG

# Check graph exists
redis-cli GRAPH.QUERY code_atlas "RETURN 1"

# Monitor disk space
df -h

# Check Docker resource usage
docker stats
```

### Metrics to Track

1. **Pipeline Metrics**:
   - Sessions processed per run
   - Average processing time per session
   - Extraction success rate
   - Cost per session (LLM mode)

2. **Graph Metrics**:
   - Total sessions in graph
   - Total entities (files, concepts, etc.)
   - Total relationships
   - Graph size (bytes)

3. **System Metrics**:
   - FalkorDB memory usage
   - Disk space used
   - API rate limit headroom
   - Error rates

### Logging

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uv run code-atlas run --limit 5

# Save logs to file
uv run code-atlas run --limit 100 > logs/pipeline.log 2>&1

# View FalkorDB logs
docker compose logs -f falkordb

# Rotate logs
logrotate /etc/logrotate.d/code-atlas
```

### Cost Tracking

```python
# Example cost tracking script
from code_atlas.pipeline import PipelineRunner
from code_atlas.config import AtlasSettings

settings = AtlasSettings()
runner = PipelineRunner(...)
stats = runner.run(limit=100)

print(f"Sessions processed: {stats.sessions_processed}")
print(f"Total cost: ${stats.estimated_cost_usd:.2f}")
print(f"Cost per session: ${stats.estimated_cost_usd / stats.sessions_processed:.4f}")
```

## Backup & Recovery

### Backing Up FalkorDB

```bash
# Method 1: Redis SAVE command
redis-cli SAVE
cp /var/lib/redis/dump.rdb backups/dump-$(date +%Y%m%d).rdb

# Method 2: Docker volume backup
docker run --rm -v code-atlas_falkordb_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/falkordb-$(date +%Y%m%d).tar.gz /data

# Method 3: Export to Cypher
redis-cli --raw GRAPH.QUERY code_atlas "MATCH (n) RETURN n" > backup.cypher
```

### Automated Backup Script

```bash
#!/bin/bash
# backup-atlas.sh

DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/backups/code-atlas"
mkdir -p "$BACKUP_DIR"

# Backup FalkorDB
docker exec code-atlas-falkordb redis-cli SAVE
docker cp code-atlas-falkordb:/data/dump.rdb \
  "$BACKUP_DIR/dump-$DATE.rdb"

# Backup config
cp .code-atlas.toml "$BACKUP_DIR/config-$DATE.toml"

# Compress old backups
find "$BACKUP_DIR" -name "dump-*.rdb" -mtime +7 -exec gzip {} \;

# Delete backups older than 30 days
find "$BACKUP_DIR" -name "dump-*.rdb.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/dump-$DATE.rdb"
```

### Restoring from Backup

```bash
# 1. Stop services
docker compose down

# 2. Restore dump file
docker run --rm -v code-atlas_falkordb_data:/data \
  -v $(pwd)/backups:/backup \
  alpine sh -c "cd /data && tar xzf /backup/falkordb-20250101.tar.gz --strip 1"

# Or for .rdb file:
docker run --rm -v code-atlas_falkordb_data:/data \
  -v $(pwd)/backups:/backup \
  alpine cp /backup/dump-20250101.rdb /data/dump.rdb

# 3. Restart services
docker compose up -d

# 4. Verify data
uv run code-atlas report
```

### Disaster Recovery

**Scenario**: Complete data loss

1. **Restore from backup** (see above)
2. **If no backup**: Re-run pipeline on original sessions
   ```bash
   uv run code-atlas run --no-dry-run --use-llm --limit 1000
   ```
3. **Verify data integrity**:
   ```bash
   uv run code-atlas report
   redis-cli GRAPH.QUERY code_atlas "MATCH (n) RETURN count(n)"
   ```

## Security

### API Key Management

```bash
# Store in environment (never commit)
export ANTHROPIC_API_KEY=sk-ant-...

# Or use secret management
aws secretsmanager get-secret-value --secret-id code-atlas/api-key

# Rotate keys regularly
# 1. Generate new key in Anthropic console
# 2. Update environment variable
# 3. Test with dry run
# 4. Deploy to production
# 5. Revoke old key
```

### Network Security

```yaml
# docker-compose.prod.yml
services:
  falkordb:
    # Bind to localhost only
    ports:
      - "127.0.0.1:6379:6379"

    # Enable password auth
    environment:
      - REDIS_PASSWORD=${FALKORDB_PASSWORD}
```

### Access Control

```bash
# Use firewall to restrict access
sudo ufw allow from 10.0.0.0/8 to any port 6379

# Or use Docker network isolation
docker network create --internal code-atlas-internal
```

## Performance Tuning

### Batch Size Recommendations

| Scenario | Batch Size | Processing Time | Cost |
|----------|-----------|----------------|------|
| Initial load | 1000 | ~30min | $15 |
| Daily updates | 50-100 | ~5min | $1.50 |
| Real-time | 10-20 | ~1min | $0.30 |
| Testing | 5 | <1min | $0.10 |

### Optimization Tips

1. **Use heuristics first**, then LLM for important sessions
2. **Filter by project** to reduce processing
3. **Increase batch size** for better throughput
4. **Monitor costs** with dry runs before production
5. **Cache results** to avoid re-processing

### Concurrent Processing

**Future Enhancement**: Currently sequential, but can be parallelized:

```python
# Planned feature
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(runner.process_session, session)
        for session in sessions
    ]
```

## Alerting

### Example Prometheus Metrics

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge

sessions_processed = Counter('atlas_sessions_processed_total', 'Total sessions processed')
extraction_duration = Histogram('atlas_extraction_duration_seconds', 'Extraction duration')
cost_gauge = Gauge('atlas_cost_usd', 'Current cumulative cost')
error_counter = Counter('atlas_errors_total', 'Total errors', ['type'])
```

### Health Check Endpoint

```python
# health.py
from fastapi import FastAPI
import redis

app = FastAPI()

@app.get("/health")
def health_check():
    try:
        client = redis.Redis(host="localhost", port=6379)
        client.ping()
        return {"status": "healthy", "falkordb": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 503
```

## Support

For issues not covered in this runbook:

1. Check [GitHub Issues](https://github.com/codeswiftr-com/code-atlas/issues)
2. Review [Architecture Docs](1_active_context.md)
3. Enable debug logging: `export LOG_LEVEL=DEBUG`
4. Create minimal reproduction case
5. Open GitHub issue with logs

## Appendix

### Useful Commands

```bash
# Quick health check
docker compose ps && redis-cli ping

# View graph schema
redis-cli GRAPH.QUERY code_atlas "CALL db.labels()" --raw

# Count all nodes
redis-cli GRAPH.QUERY code_atlas "MATCH (n) RETURN count(n)"

# Find orphaned nodes (no relationships)
redis-cli GRAPH.QUERY code_atlas "MATCH (n) WHERE NOT (n)--() RETURN n"

# Delete graph (careful!)
redis-cli GRAPH.DELETE code_atlas

# Export all sessions
redis-cli GRAPH.QUERY code_atlas "MATCH (s:Session) RETURN s" --csv > sessions.csv
```

### Environment Template

```bash
# .env.template
# Copy to .env and fill in values

# API Keys
ANTHROPIC_API_KEY=

# Discovery
CODE_ATLAS_CLAUDE_ROOT=~/.claude/projects
CODE_ATLAS_MAX_SESSION_MB=50

# Extraction
CODE_ATLAS_MAX_COST_PER_SESSION=0.02
CODE_ATLAS_MAX_CUMULATIVE_COST=10.0

# Graph
CODE_ATLAS_REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO
```
