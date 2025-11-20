# Database Indexing Strategy for Code Atlas

This document describes the comprehensive database indexing strategy implemented to optimize query performance in Code Atlas FalkorDB knowledge graph.

## Overview

Code Atlas processes Claude Code sessions and converts them into a searchable FalkorDB knowledge graph. As the system scales to production workloads, database indexing becomes critical for maintaining query performance, especially for the CLI report command and other analytical queries.

## Index Categories

### 1. Session Indexes

Session indexes optimize queries that filter or retrieve session data:

```cypher
-- Session ID lookup (primary key for session nodes)
CREATE INDEX session_id IF NOT EXISTS FOR (s:Session) ON (s.id)

-- Project-based filtering
CREATE INDEX session_project IF NOT EXISTS FOR (s:Session) ON (s.project)

-- Temporal queries (recent sessions, time-based analysis)
CREATE INDEX session_modified_at IF NOT EXISTS FOR (s:Session) ON (s.modified_at)

-- Size-based queries (analyzing session sizes)
CREATE INDEX session_size_bytes IF NOT EXISTS FOR (s:Session) ON (s.size_bytes)
```

**Usage patterns:**
- Session lookup by ID: `MATCH (s:Session {id:'session_id'})`
- Project filtering: `MATCH (s:Session {project:'project_name'})`
- Recent sessions: `MATCH (s:Session) ORDER BY s.modified_at DESC`
- Session statistics: `MATCH (s:Session) RETURN AVG(s.size_bytes)`

### 2. Entity Indexes

Entity indexes optimize lookups for Files, Concepts, and other entity types:

```cypher
-- File entity indexes
CREATE INDEX entity_id IF NOT EXISTS FOR (e:File) ON (e.id)
CREATE INDEX entity_name IF NOT EXISTS FOR (e:File) ON (e.name)
CREATE INDEX entity_type IF NOT EXISTS FOR (e:File) ON (e.type)

-- Concept entity indexes
CREATE INDEX entity_id IF NOT EXISTS FOR (e:Concept) ON (e.id)
CREATE INDEX entity_name IF NOT EXISTS FOR (e:Concept) ON (e.name)
CREATE INDEX entity_type IF NOT EXISTS FOR (e:Concept) ON (e.type)
```

**Usage patterns:**
- File lookups: `MATCH (f:File {name:'src/app.py'})`
- Concept queries: `MATCH (c:Concept {name:'authentication'})`
- Entity type filtering: `MATCH (e:File) WHERE e.type = 'file'`

### 3. Insight Indexes

Insight indexes optimize retrieval of extracted insights:

```cypher
-- Insight lookup by ID
CREATE INDEX insight_id IF NOT EXISTS FOR (i:Insight) ON (i.id)
```

**Usage patterns:**
- Insight retrieval: `MATCH (i:Insight {id:'insight_id'})`
- Session insights: `MATCH (s:Session)-[:HAS_INSIGHT]->(i:Insight)`

### 4. Relationship Indexes

Relationship indexes optimize traversal queries across relationships:

```cypher
-- MENTIONS relationship indexes
CREATE INDEX mentions_source IF NOT EXISTS FOR ()-[r:MENTIONS]->() ON (r.confidence)
CREATE INDEX mentions_extracted_at IF NOT EXISTS FOR ()-[r:MENTIONS]->() ON (r.extracted_at)
```

**Usage patterns:**
- High-confidence relationships: `MATCH ()-[r:MENTIONS]->() WHERE r.confidence > 0.8`
- Recent extractions: `MATCH ()-[r:MENTIONS]->() WHERE r.extracted_at > timestamp`

### 5. Full-Text Indexes

Full-text indexes enable efficient text search across entity names:

```cypher
-- Full-text search on entity names
CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS FOR (e) ON EACH [e.name]
```

**Usage patterns:**
- Text search: `CALL db.index.fulltext.queryNodes('entity_name_fulltext', 'search_term')`
- Fuzzy matching: `CALL db.index.fulltext.queryNodes('entity_name_fulltext', 'auth*')`

## Query Optimization Examples

### Report Command Optimization

The CLI report command benefits from multiple indexes:

```cypher
-- Before: Full table scan
MATCH (f:File)<-[r:MENTIONS]-()
RETURN f.name, COUNT(r) AS mentions
ORDER BY mentions DESC
LIMIT 10

-- After: Uses entity_name index and relationship traversal
-- 1. entity_name index helps locate File nodes
-- 2. mentions_source index helps filter relationship traversal
```

```cypher
-- Session statistics query optimized
MATCH (s:Session)
RETURN COUNT(s) AS total_sessions,
       AVG(s.size_bytes) AS avg_size,
       SUM(s.size_bytes) AS total_size
-- Uses session_modified_at and session_size_bytes indexes
```

```cypher
-- Recent sessions query optimized
MATCH (s:Session)
RETURN s.id, s.project, s.modified_at
ORDER BY s.modified_at DESC
LIMIT 10
-- Uses session_modified_at index for efficient sorting
```

## Performance Impact

### Expected Performance Improvements

| Query Type | Without Indexes | With Indexes | Improvement |
|------------|----------------|--------------|-------------|
| Session ID lookup | O(n) full scan | O(log n) index seek | ~100-1000x |
| File name search | O(n) full scan | O(log n) index seek | ~100-1000x |
| Project filtering | O(n) full scan | O(log n) range scan | ~50-500x |
| Recent sessions | O(n log n) sort | O(log n) indexed sort | ~10-100x |
| Top files by mentions | O(n²) traversal | O(n log m) indexed | ~10-50x |

### Memory Overhead

Indexes consume additional memory, but the trade-off is favorable for production:

- **Session indexes**: ~10-20 bytes per session
- **Entity indexes**: ~15-30 bytes per entity
- **Relationship indexes**: ~8-15 bytes per relationship
- **Full-text indexes**: ~20-40 bytes per entity name

For a typical production workload with:
- 10,000 sessions
- 100,000 entities
- 500,000 relationships

Expected additional memory usage: ~50-100MB for indexes vs ~1-2GB for data (5-10% overhead).

## Configuration Options

### Environment Variables

```bash
# Enable/disable automatic index creation
CODE_ATLAS_CREATE_INDEXES=true

# Timeout for index creation operations (seconds)
CODE_ATLAS_INDEX_TIMEOUT=30

# Verify indexes after creation
CODE_ATLAS_VERIFY_INDEXES=true
```

### Configuration File (.code-atlas.toml)

```toml
[database]
create_indexes = true
index_timeout = 30
verify_indexes = true
```

### Runtime Configuration

```python
from code_atlas.graph_populator import GraphPopulator

# Custom configuration
populator = GraphPopulator(
    graph_name="code_atlas",
    create_indexes=True,
    index_timeout=60,
    verify_indexes_after_creation=True
)
```

## Index Management

### Automatic Creation

Indexes are created automatically when `GraphPopulator` is initialized (unless disabled):

```python
# Creates indexes during initialization
populator = GraphPopulator(dry_run=False, create_indexes=True)
```

### Manual Index Management

```python
# List all defined indexes
indexes = populator.list_indexes()

# Verify existing indexes
status = populator.verify_indexes()

# Drop all indexes (useful for testing)
populator.drop_indexes()
```

### Index Creation Patterns

Indexes use `IF NOT EXISTS` to be idempotent:

```cypher
CREATE INDEX session_id IF NOT EXISTS FOR (s:Session) ON (s.id)
```

This allows safe re-execution during deployments and testing.

## Monitoring and Maintenance

### Index Usage Monitoring

Monitor index effectiveness through query performance:

```python
# Benchmark queries with and without indexes
import time

def benchmark_query(query: str) -> float:
    start = time.time()
    result = client.execute_command("GRAPH.QUERY", graph_name, query)
    return time.time() - start
```

### Index Maintenance

- **Rebuilding**: Indexes are automatically maintained by FalkorDB
- **Statistics**: FalkorDB updates index statistics automatically
- **Fragmentation**: Minimal in FalkorDB due to append-only nature

## Testing Strategy

### Unit Tests

- Verify index definitions are correct
- Test index creation in dry-run mode
- Validate configuration options

### Integration Tests

- Test index creation with real FalkorDB
- Verify query performance improvements
- Test index management operations

### Performance Tests

- Benchmark common queries with/without indexes
- Measure memory usage impact
- Test with production-scale data

## Best Practices

### Development

1. **Enable indexes in development**: Use `create_indexes=True` to catch issues early
2. **Dry-run testing**: Use `dry_run=True` to verify index creation queries
3. **Test with real data**: Use integration tests with actual FalkorDB

### Production

1. **Always enable indexes**: Set `CODE_ATLAS_CREATE_INDEXES=true`
2. **Monitor query performance**: Set up alerts for slow queries
3. **Verify index creation**: Use `verify_indexes=true` during deployment

### Performance Tuning

1. **Query profiling**: Use FalkorDB's `EXPLAIN` to verify index usage
2. **Index coverage**: Ensure common query patterns have appropriate indexes
3. **Memory monitoring**: Track memory usage with indexes

## Troubleshooting

### Common Issues

**Issue: Index creation fails**
- **Cause**: Insufficient permissions or disk space
- **Solution**: Check FalkorDB logs, ensure sufficient resources

**Issue: Queries still slow after indexing**
- **Cause**: Missing indexes for specific query patterns
- **Solution**: Analyze query patterns, add missing indexes

**Issue: Index creation timeout**
- **Cause**: Large dataset or slow storage
- **Solution**: Increase `index_timeout`, create indexes in batches

### Debugging

```python
# Check if indexes are being used
populator = GraphPopulator()
status = populator.verify_indexes()
print("Index status:", status)

# Check executed queries
print("Index creation queries:",
      [q for q in populator.executed_queries if "CREATE INDEX" in q])
```

## Future Enhancements

### Planned Improvements

1. **Adaptive Indexing**: Automatically create indexes based on query patterns
2. **Partial Indexes**: Create indexes for frequently accessed subsets
3. **Composite Indexes**: Multi-column indexes for complex queries
4. **Index Statistics**: Track index usage patterns for optimization

### Advanced Features

1. **Query Plan Analysis**: Automatic optimization suggestions
2. **Index Health Monitoring**: Detect and repair corrupted indexes
3. **Performance Regression Testing**: Automated performance testing

## Migration Guide

### From Non-Indexed Setup

Existing Code Atlas installations can be upgraded without data loss:

1. **Backup existing data**: `GRAPH.DUMP code_atlas > backup.json`
2. **Update Code Atlas**: Pull latest version with index support
3. **Run with indexes**: Set `CODE_ATLAS_CREATE_INDEXES=true`
4. **Verify functionality**: Test queries and reports

### Rollback Plan

If indexes cause issues:

```python
# Disable indexes temporarily
populator = GraphPopulator(create_indexes=False)

# Or drop existing indexes
populator.drop_indexes()
```

---

This indexing strategy provides a solid foundation for production-scale Code Atlas deployments, ensuring fast query performance while maintaining data integrity and system reliability.