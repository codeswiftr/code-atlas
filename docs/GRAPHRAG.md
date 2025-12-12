# GraphRAG Documentation

This document describes the GraphRAG (Retrieval-Augmented Generation) features in Code Atlas, which enable natural language question answering over the knowledge graph.

## Overview

GraphRAG combines semantic search (vector embeddings) with structural graph queries to provide intelligent question answering. It allows users to ask natural language questions about their codebase and get answers based on the knowledge graph.

## Features

### 1. Entity Embeddings
- Automatic embedding generation for all entities using sentence-transformers
- Embeddings capture semantic meaning of entity names and descriptions
- Supports multiple embedding models (configurable)

### 2. Hybrid Search
- Combines Cypher graph queries with vector similarity search
- Weighted ranking algorithm balances graph structure and semantic similarity
- Configurable weights for graph vs. vector scores

### 3. RAG Question Answering
- Natural language question processing
- Context retrieval from knowledge graph
- Answer generation using LLM (with fallback to rule-based answers)

## API Endpoints

### POST /api/v1/graph/hybrid-search

Perform hybrid search combining graph structure and semantic similarity.

**Request:**
```json
{
  "query": "authentication systems",
  "entity_type": "Concept",
  "limit": 20,
  "min_score": 0.3,
  "graph_weight": 0.4,
  "vector_weight": 0.6,
  "use_graph_structure": true,
  "use_vector_search": true
}
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "entity_id": "concept-abc123",
      "entity_name": "Authentication",
      "entity_type": "Concept",
      "graph_score": 0.8,
      "vector_score": 0.9,
      "combined_score": 0.86,
      "metadata": {}
    }
  ],
  "total": 1,
  "query": "authentication systems",
  "execution_time_ms": 45.2,
  "message": "Hybrid search found 1 results"
}
```

### POST /api/v1/insights/rag/query

Answer a natural language question using RAG.

**Request:**
```json
{
  "question": "What problems keep recurring in my sessions?",
  "entity_type": "Problem",
  "context_limit": 5,
  "include_sources": true
}
```

**Response:**
```json
{
  "success": true,
  "answer": "Based on the knowledge graph, I found several recurring problems...",
  "sources": ["problem-1", "problem-2"],
  "confidence": 0.85,
  "context_entities": [
    {
      "entity_id": "problem-1",
      "entity_name": "Database Connection Issues",
      "entity_type": "Problem"
    }
  ],
  "search_results_count": 3,
  "execution_time_ms": 234.5,
  "message": "Question answered successfully"
}
```

## CLI Usage

### Interactive Query Mode

```bash
code-atlas query --interactive
```

Opens an interactive prompt where you can ask questions:

```
Question: What tools are most commonly used?
[Answer is displayed with sources and confidence]
```

### Single Query

```bash
code-atlas query "What problems keep recurring?" --entity-type Problem
```

## Configuration

### Embedding Model

Configure the embedding model in `.code-atlas.toml`:

```toml
[embeddings]
model_name = "all-MiniLM-L6-v2"  # Fast, good quality
# model_name = "all-mpnet-base-v2"  # Slower, higher quality
cache_dir = "~/.cache/code-atlas-embeddings"
```

### Vector Storage

Choose vector storage backend:

```toml
[vector_store]
type = "falkordb"  # Store in FalkorDB (default)
# type = "external"  # Use external vector DB
# connection_string = "qdrant://localhost:6333"
```

### Hybrid Search Weights

Configure search weighting:

```toml
[hybrid_search]
graph_weight = 0.4    # Weight for graph structure scores
vector_weight = 0.6   # Weight for vector similarity scores
```

## Architecture

### Components

1. **EmbeddingGenerator** (`embeddings.py`)
   - Generates embeddings using sentence-transformers
   - Supports batch processing
   - Caches model for performance

2. **VectorStore** (`vector_store.py`)
   - Abstract interface for vector storage
   - Implementations: FalkorDBVectorStore, ExternalVectorStore
   - Stores and retrieves embeddings

3. **HybridSearch** (`hybrid_search.py`)
   - Combines graph queries with vector search
   - Weighted ranking algorithm
   - Returns unified results

4. **RAGService** (`rag_service.py`)
   - Orchestrates question answering pipeline
   - Retrieves context from graph
   - Generates answers using LLM or fallback

### Data Flow

```
Question → EmbeddingGenerator → VectorStore.search()
                                ↓
                        HybridSearch.search()
                                ↓
                        Context Retrieval
                                ↓
                        RAGService.answer_question()
                                ↓
                        LLM Answer Generation
                                ↓
                        Answer + Sources
```

## Performance Considerations

- **Embedding Generation**: First-time generation can be slow. Embeddings are cached.
- **Vector Search**: In-memory similarity calculation for FalkorDB. Consider external vector DB for large graphs.
- **LLM Integration**: Requires API key and incurs costs. Fallback mode available without LLM.

## Limitations

- LLM integration is currently a placeholder - requires implementation
- Vector search uses in-memory calculation (not optimized for large graphs)
- Embeddings generated on-demand (no background indexing)

## Future Improvements

- Background embedding generation during entity creation
- Integration with external vector databases (Qdrant, Weaviate)
- Full LLM integration with multiple providers
- Embedding caching and persistence
- Performance optimizations for large graphs
