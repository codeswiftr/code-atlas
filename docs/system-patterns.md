# System Patterns · Code Atlas

## Architecture Overview
```
┌─────────────────────────────────────────────────────────────────────┐
│                         CODE ATLAS DATA FLOW                        │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Session Discovery                                                │
│    • Scan ~/.claude/projects/**/sessions/*.jsonl                    │
│    • Filter by project/date/token thresholds                        │
│                                                                     │
│ 2. Streaming Parser                                                 │
│    • Read JSONL line-by-line → normalize turns                      │
│    • Outputs canonical Conversation object (messages, metadata)     │
│                                                                     │
│ 3. Insight Extraction Engine                                        │
│    • Prompt Claude / Llama for entities + relationships             │
│    • Applies guardrails + heuristics                                │
│                                                                     │
│ 4. Knowledge Graph Populator                                        │
│    • Upserts nodes/edges into FalkorDB                              │
│    • Maintains provenance + TTL policies                            │
│                                                                     │
│ 5. Query / Delivery Layer                                           │
│    • Cypher, GraphQL, GraphRAG APIs                                 │
│    • Dashboards + CLI reports                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Components
| Component | Description | Tech |
| --- | --- | --- |
| `SessionDiscovery` | Walks Claude project directories, emits session metadata events. Supports allow/deny lists and incremental checkpoints. | Python pathlib, watchfiles |
| `SessionParser` | Streams JSONL, maps to typed dataclasses (UserMessage, AssistantMessage, ToolCall). Calculates timing, tokens, referenced files. | Python `json`, `pydantic` |
| `InsightExtractor` | Sends curated prompt to LLM, receives structured JSON (entities, relationships, insights). Validates schema + confidence scores. | Anthropic API / Ollama, Guardrails |
| `GraphPopulator` | Connects to FalkorDB via RESP/Redis driver, executes OpenCypher queries to upsert nodes/edges, attaches provenance. | `falkordb` Python client |
| `MetricsEmitter` | Emits Prometheus counters, histograms, and structured logs per stage. | `prometheus_client`, OpenTelemetry |
| `Query API` (Phase 2) | Thin FastAPI service for Cypher proxy, GraphRAG endpoint, and Slack/MCP integrations. | FastAPI, LlamaIndex |

## Data Model (MVP)
### Nodes
- `Session {session_id, project, path, started_at, duration, model, token_count, status}`
- `Message {message_id, role, timestamp, token_count}`
- `Concept {concept_id, name, type, description, first_seen, last_seen}`
- `File {path, repo, language, last_modified}`
- `Tool {name, version, capability}`
- `Problem {title, severity, category}`
- `Solution {title, technique, confidence}`

### Relationships
- `Session-[:CONTAINS]->Message`
- `Message-[:MENTIONS]->Concept|File|Problem|Solution|Tool`
- `Problem-[:SOLVED_BY]->Solution`
- `Concept-[:RELATED_TO]->Concept`
- `Solution-[:USES_TOOL]->Tool`
- `Session-[:DERIVES_FROM]->Session` (for incremental updates)

## Data Flow Notes
1. **File Access**: default path `~/.claude/projects` configurable via env; discovery respects `.code-atlas-ignore`.
2. **Streaming**: Parser never loads entire JSONL; supports >100MB sessions.
3. **Prompting**: InsightExtractor sends entire conversation chunked into 12k token windows with sliding overlap. Response must conform to JSON schema enforced via Guardrails.
4. **Graph Writes**: Use `MERGE` statements with deterministic IDs (hashes) to avoid duplication. TTL policies implemented with `EXPIRE` metadata for low-value nodes.
5. **Monitoring**: Each stage emits spans (`code_atlas.session.parse`, `code_atlas.graph.upsert`) for tracing through OTLP.

## Operational Patterns
- **Batch CLI**: `code_atlas run --days-back 7 --batch-size 20`.
- **Scheduler**: optional cron or GitHub Actions runner to invoke CLI daily.
- **Error Handling**: failed sessions retried up to 3 times; after that they move to `quarantine/` with reason code for manual review.
- **Security**: allowlist of directories; optional regex-based redaction of secrets before LLM call; encryption at rest for temp artifacts.

## Future Enhancements
- Graph embeddings + hybrid search (FalkorDB native or pgvector)
- Web console for session status + Cypher notebook
- MCP tool exposing graph queries back to Claude Code
- Connectors for non-Claude sources (GitHub Copilot, Slack threads)
