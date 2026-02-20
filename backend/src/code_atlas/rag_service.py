"""RAG (Retrieval-Augmented Generation) service for question answering.

Provides natural language question answering over the knowledge graph by:
1. Converting question to embedding
2. Performing hybrid search to find relevant entities
3. Retrieving context from graph
4. Generating answer using LLM with retrieved context
"""

from __future__ import annotations

from typing import Any

from anthropic import APIError

from .hybrid_search import HybridSearch
from .logging_config import get_logger

logger = get_logger(__name__)

# Haiku pricing (per 1M tokens) - cost-effective for Q&A
HAIKU_INPUT_COST = 0.25  # $0.25 per 1M input tokens
HAIKU_OUTPUT_COST = 1.25  # $1.25 per 1M output tokens
DEFAULT_RAG_MODEL = "claude-3-haiku-20240307"
DEFAULT_MAX_TOKENS = 1024


class RAGService:
    """RAG service for question answering over knowledge graph."""

    def __init__(
        self,
        graph_populator: Any,
        hybrid_search: HybridSearch,
        llm_client: Any | None = None,
        context_limit: int = 5,
    ) -> None:
        """Initialize RAG service.

        Args:
            graph_populator: GraphPopulator instance for graph queries.
            hybrid_search: HybridSearch instance for entity retrieval.
            llm_client: LLM client for answer generation (Anthropic, etc.).
            context_limit: Maximum number of entities to use as context.
        """
        self.graph = graph_populator
        self.hybrid_search = hybrid_search
        self.llm_client = llm_client
        self.context_limit = context_limit
        logger.info("RAG service initialized", context_limit=context_limit)

    def answer_question(
        self,
        question: str,
        entity_type: str | None = None,
        include_sources: bool = True,
    ) -> dict[str, Any]:
        """Answer a natural language question using RAG.

        Args:
            question: Natural language question to answer.
            entity_type: Optional filter by entity type.
            include_sources: Whether to include source entity citations.

        Returns:
            Dictionary with 'answer', 'sources', and 'confidence' fields.
        """
        logger.info("Processing RAG question", question=question[:100])

        try:
            # Step 1: Retrieve relevant entities using hybrid search
            search_results = self.hybrid_search.search(
                query=question,
                entity_type=entity_type,
                limit=self.context_limit,
                min_score=0.3,  # Lower threshold for RAG context
            )

            if not search_results:
                return {
                    "answer": (
                        "I couldn't find relevant information in the knowledge graph"
                        " to answer this question."
                    ),
                    "sources": [],
                    "confidence": 0.0,
                    "context_entities": [],
                }

            # Step 2: Retrieve full context for top entities
            context_entities = []
            source_ids = []

            for result in search_results[:self.context_limit]:
                entity_details = self._get_entity_context(result.entity_id, result.entity_type)
                if entity_details:
                    context_entities.append(entity_details)
                    source_ids.append(result.entity_id)

            # Step 3: Build context string for LLM
            context_text = self._build_context_string(context_entities)

            # Step 4: Generate answer using LLM (if available)
            if self.llm_client:
                answer = self._generate_answer_with_llm(question, context_text)
                confidence = self._calculate_confidence(search_results)
            else:
                # Fallback: Construct simple answer from context
                answer = self._generate_answer_from_context(question, context_entities)
                confidence = 0.6  # Lower confidence without LLM

            return {
                "answer": answer,
                "sources": source_ids if include_sources else [],
                "confidence": confidence,
                "context_entities": [
                    {
                        "entity_id": e["entity_id"],
                        "entity_name": e["entity_name"],
                        "entity_type": e["entity_type"],
                    }
                    for e in context_entities
                ],
                "search_results_count": len(search_results),
            }

        except Exception as exc:
            logger.error("RAG question answering failed", error=str(exc))
            return {
                "answer": f"An error occurred while processing your question: {str(exc)}",
                "sources": [],
                "confidence": 0.0,
                "context_entities": [],
            }

    def _get_entity_context(self, entity_id: str, entity_type: str) -> dict[str, Any] | None:
        """Get full context for an entity including relationships."""
        # Get entity details
        query = """
            MATCH (e {id: $entity_id})
            OPTIONAL MATCH (e)-[r]-(related)
            RETURN e, labels(e) as labels,
                   collect(DISTINCT {
                       rel_type: type(r), target: related.name,
                       target_type: labels(related)[0]
                   }) as relationships
            LIMIT 1
        """
        try:
            results = self.graph.execute_query(query, {"entity_id": entity_id})
            if not results:
                return None

            row = results[0]
            node = row.get("e", {})
            labels = row.get("labels", [])
            relationships = row.get("relationships", [])

            return {
                "entity_id": entity_id,
                "entity_name": node.get("name", node.get("title", entity_id)),
                "entity_type": labels[0] if labels else entity_type,
                "properties": dict(node),
                "relationships": relationships[:10],  # Limit relationships
            }
        except Exception as exc:
            logger.warning("Failed to get entity context", entity_id=entity_id, error=str(exc))
            return None

    def _build_context_string(self, context_entities: list[dict[str, Any]]) -> str:
        """Build context string from retrieved entities."""
        context_parts = []

        for entity in context_entities:
            name = entity.get("entity_name", "Unknown")
            entity_type = entity.get("entity_type", "Concept")
            props = entity.get("properties", {})
            relationships = entity.get("relationships", [])

            # Build entity description
            entity_desc = f"Entity: {name} (Type: {entity_type})"
            if props.get("description"):
                entity_desc += f"\nDescription: {props['description']}"
            if relationships:
                rels_str = ", ".join([f"{r.get('target', '')}" for r in relationships[:5]])
                entity_desc += f"\nRelated to: {rels_str}"

            context_parts.append(entity_desc)

        return "\n\n".join(context_parts)

    def _generate_answer_with_llm(
        self,
        question: str,
        context: str,
    ) -> str:
        """Generate answer using LLM with context.

        Uses Anthropic Claude Haiku for cost-effective Q&A generation.
        Falls back to context-based answer on API errors.
        """
        if not self.llm_client:
            return self._generate_answer_from_context_simple(question, context)

        # Build prompt for LLM
        user_prompt = f"""Context from knowledge graph:
{context}

Question: {question}

Based on the context provided, please answer the question.
If the context doesn't contain enough information, say so.
Be concise and cite specific entities when relevant."""

        system_prompt = (
            "You are a helpful assistant answering questions about a codebase knowledge graph."
            " You have access to entities, relationships, and metadata extracted from coding"
            " sessions. Answer questions based solely on the provided context."
            " Be accurate and concise."
        )

        try:
            logger.info("Generating RAG answer with LLM", model=DEFAULT_RAG_MODEL)

            response = self.llm_client.messages.create(
                model=DEFAULT_RAG_MODEL,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Extract answer from response
            answer = response.content[0].text

            # Log token usage for cost tracking
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = self._estimate_rag_cost(input_tokens, output_tokens)

            logger.info(
                "RAG answer generated",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost,
            )

            return answer

        except APIError as exc:
            logger.warning("Anthropic API error, using fallback", error=str(exc))
            return self._generate_answer_from_context_simple(question, context)
        except Exception as exc:
            logger.warning("LLM generation failed, using fallback", error=str(exc))
            return self._generate_answer_from_context_simple(question, context)

    def _estimate_rag_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for RAG query based on Haiku pricing."""
        input_cost = (input_tokens / 1_000_000) * HAIKU_INPUT_COST
        output_cost = (output_tokens / 1_000_000) * HAIKU_OUTPUT_COST
        return input_cost + output_cost

    def _generate_answer_from_context(
        self,
        question: str,
        context_entities: list[dict[str, Any]],
    ) -> str:
        """Generate simple answer from context without LLM."""
        if not context_entities:
            return "I couldn't find relevant information to answer this question."

        # Build simple answer from entity names and types
        entity_names = [e.get("entity_name", "") for e in context_entities]
        answer = (
            f"Based on the knowledge graph, I found {len(context_entities)} relevant entities:"
            f" {', '.join(entity_names[:5])}."
        )

        if len(context_entities) > 5:
            answer += f" And {len(context_entities) - 5} more."

        return answer

    def _generate_answer_from_context_simple(self, question: str, context: str) -> str:
        """Generate simple answer from context text."""
        if not context:
            return "I couldn't find relevant information to answer this question."

        # Simple extraction: mention entities found
        lines = context.split("\n\n")
        entity_count = len([line for line in lines if line.startswith("Entity:")])

        return (
            f"Based on the knowledge graph, I found {entity_count} relevant entities"
            f" that might help answer your question. {context[:200]}..."
        )

    def _calculate_confidence(self, search_results: list[Any]) -> float:
        """Calculate confidence score based on search results."""
        if not search_results:
            return 0.0

        # Average combined score of top results
        avg_score = sum(r.combined_score for r in search_results[:3]) / min(3, len(search_results))
        return float(avg_score)


def create_rag_service(
    graph_populator: Any,
    vector_store: Any,
    llm_client: Any | None = None,
) -> RAGService:
    """Factory function to create RAG service instance.

    Args:
        graph_populator: GraphPopulator instance.
        vector_store: VectorStore instance.
        llm_client: Optional LLM client for answer generation.

    Returns:
        RAGService instance.
    """
    from .hybrid_search import HybridSearch

    hybrid_search = HybridSearch(
        graph_populator=graph_populator,
        vector_store=vector_store,
    )

    return RAGService(
        graph_populator=graph_populator,
        hybrid_search=hybrid_search,
        llm_client=llm_client,
    )
