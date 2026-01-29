"""LLM-backed (or heuristic) extraction of entities and relationships."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from anthropic import Anthropic, APIError
from litellm import completion, completion_cost
from pydantic import BaseModel, Field, ValidationError

from .exceptions import CostLimitExceeded
from .logging_config import get_logger
from .metrics import AtlasMetrics
from .models import ParsedSession, SessionMessage

logger = get_logger(__name__)

EntityType = Literal["concept", "file", "tool", "problem", "solution"]
LLMProvider = Literal["anthropic", "openrouter"]

# Anthropic pricing as of 2025 (per 1M tokens)
# Source: https://www.anthropic.com/api
CLAUDE_SONNET_INPUT_COST = 3.00  # $3 per 1M input tokens
CLAUDE_SONNET_OUTPUT_COST = 15.00  # $15 per 1M output tokens
CLAUDE_HAIKU_INPUT_COST = 0.25  # $0.25 per 1M input tokens
CLAUDE_HAIKU_OUTPUT_COST = 1.25  # $1.25 per 1M output tokens


class Entity(BaseModel):
    type: EntityType
    name: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Relationship(BaseModel):
    type: str
    source: str
    target: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    estimated_cost_usd: float = 0.0
    extracted_at: str | None = None  # ISO timestamp of extraction
    extractor_model: str | None = None  # Model used for extraction
    extraction_method: str = "heuristic"  # "llm" or "heuristic"


@dataclass
class CostGuard:
    """Enforces cost limits for LLM API usage."""

    max_session: float
    max_cumulative: float
    cumulative: float = 0.0

    def check_session(self, estimated_cost: float) -> bool:
        """Return True if session is within limit."""
        return estimated_cost <= self.max_session

    def record(self, actual_cost: float) -> None:
        """Record cost and check cumulative limit."""
        self.cumulative += actual_cost
        logger.debug(
            "Cost recorded",
            actual_cost_usd=actual_cost,
            cumulative_cost_usd=self.cumulative,
        )
        if self.cumulative > self.max_cumulative:
            raise CostLimitExceeded(
                f"Cumulative cost ${self.cumulative:.6f} exceeds limit ${self.max_cumulative:.2f}",
                current_cost=self.cumulative,
                limit=self.max_cumulative,
                limit_type="cumulative",
            )


@dataclass
class InsightExtractor:
    """Convert parsed sessions into graph-friendly entities/relationships."""

    model: str = "claude-3-5-sonnet-latest"
    use_llm: bool | None = None
    provider: LLMProvider | None = None
    cost_guard: CostGuard | None = None
    metrics: AtlasMetrics | None = None
    client: Anthropic | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    def __post_init__(self) -> None:
        # Check if user passed an explicit model (different from default)
        default_model = "claude-3-5-sonnet-latest"
        user_provided_model = self.model != default_model

        # Determine provider
        provider = self.provider or os.getenv("CODE_ATLAS_LLM_PROVIDER", "anthropic").lower()
        if provider not in ("anthropic", "openrouter"):
            logger.warning(
                f"Invalid provider '{provider}', defaulting to 'anthropic'",
                provider=provider,
            )
            provider = "anthropic"

        # Get API keys
        anthropic_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
        openrouter_key = self.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")

        # Get model configuration from env vars
        configured_model = os.getenv("ANTHROPIC_MODEL")
        openrouter_model = self.openrouter_model or os.getenv("OPENROUTER_MODEL")
        openrouter_base = os.getenv("CODE_ATLAS_OPENROUTER_BASE_URL", self.openrouter_base_url)

        # Provider selection logic
        if provider == "openrouter":
            if openrouter_key:
                self.provider = "openrouter"
                self.openrouter_api_key = openrouter_key
                self.openrouter_base_url = openrouter_base
                # Only override model if user didn't provide one explicitly
                if not user_provided_model:
                    if openrouter_model:
                        self.model = openrouter_model
                    elif not configured_model:
                        # Default OpenRouter model if none specified
                        self.model = "x-ai/grok-4.1-fast"
                self.client = None  # LiteLLM doesn't need a client object
            else:
                logger.warning(
                    "OpenRouter provider selected but OPENROUTER_API_KEY not found, "
                    "falling back to Anthropic or heuristics",
                )
                provider = "anthropic"

        if provider == "anthropic":
            if anthropic_key:
                self.provider = "anthropic"
                base_url = os.getenv("ANTHROPIC_BASE_URL")
                # Only override model from env if user didn't provide one explicitly
                if configured_model and not user_provided_model:
                    self.model = configured_model
                client_kwargs: dict[str, Any] = {"api_key": anthropic_key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                self.client = Anthropic(**client_kwargs)
            else:
                self.client = None
                self.provider = None

        # Fallback: if provider not explicitly set, try to auto-detect
        if not self.provider:
            if openrouter_key:
                self.provider = "openrouter"
                self.openrouter_api_key = openrouter_key
                self.openrouter_base_url = openrouter_base
                # Only override model if user didn't provide one explicitly
                if not user_provided_model:
                    if openrouter_model:
                        self.model = openrouter_model
                    elif not configured_model:
                        # Default OpenRouter model if none specified
                        self.model = "x-ai/grok-4.1-fast"
                self.client = None
            elif anthropic_key:
                self.provider = "anthropic"
                base_url = os.getenv("ANTHROPIC_BASE_URL")
                # Only override model from env if user didn't provide one explicitly
                if configured_model and not user_provided_model:
                    self.model = configured_model
                client_kwargs = {"api_key": anthropic_key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                self.client = Anthropic(**client_kwargs)
            else:
                self.provider = None
                self.client = None

        # Determine if LLM should be used
        wants_llm = self.use_llm if self.use_llm is not None else bool(self.provider)
        if not wants_llm:
            self.provider = None
            self.client = None

    def extract(self, session: ParsedSession) -> ExtractionResult:
        # Record extraction request
        if self.metrics:
            method = "llm" if self.provider else "heuristic"
            self.metrics.record_extraction_request(method, self.model)

        # Time the extraction
        context_manager = (
            self.metrics.time_extraction(method) if self.metrics else self._null_context_manager()
        )

        with context_manager:
            if self.provider:
                try:
                    return self._call_llm_with_retry(session)
                except (
                    APIError,
                    json.JSONDecodeError,
                    ValueError,
                    ValidationError,
                    CostLimitExceeded,
                    Exception,
                ) as exc:
                    # Record error metrics
                    if self.metrics:
                        self.metrics.record_error("extraction", type(exc).__name__)

                    # Fall back to heuristic extraction if structured response fails.
                    logger.warning(
                        "LLM extraction failed, falling back to heuristics",
                        session_id=session.metadata.session_id,
                        error=str(exc),
                        error_type=type(exc).__name__,
                        provider=self.provider,
                    )

                    # Record fallback extraction
                    if self.metrics:
                        self.metrics.record_extraction_request("heuristic_fallback", "heuristic")

                    return self._heuristic_extract(session)
            else:
                return self._heuristic_extract(session)

    def _null_context_manager(self):
        """Null context manager for when metrics are disabled."""
        from contextlib import nullcontext
        return nullcontext()

    def _calculate_cost(
        self, input_tokens: int, output_tokens: int, response: Any | None = None
    ) -> float:
        """Calculate API cost based on actual token usage and model pricing.
        
        For OpenRouter, uses LiteLLM's completion_cost if response is provided.
        For Anthropic, uses hardcoded pricing constants.
        """
        if self.provider == "openrouter" and response is not None:
            # Use LiteLLM's built-in cost calculation for OpenRouter
            try:
                cost = completion_cost(completion_response=response)
                return round(cost, 6)
            except Exception as exc:
                logger.warning(
                    "Failed to calculate cost using LiteLLM, falling back to estimation",
                    error=str(exc),
                    model=self.model,
                )
                # Fall through to estimation

        # Anthropic pricing or model-based estimation
        # Use Anthropic pricing when provider is "anthropic" or None (for testing/heuristic mode)
        if self.provider in ("anthropic", None):
            # Determine pricing based on model name
            if "haiku" in self.model.lower():
                input_cost_per_1m = CLAUDE_HAIKU_INPUT_COST
                output_cost_per_1m = CLAUDE_HAIKU_OUTPUT_COST
            else:  # Default to Sonnet pricing
                input_cost_per_1m = CLAUDE_SONNET_INPUT_COST
                output_cost_per_1m = CLAUDE_SONNET_OUTPUT_COST

            cost = (input_tokens / 1_000_000 * input_cost_per_1m) + (
                output_tokens / 1_000_000 * output_cost_per_1m
            )
            return round(cost, 6)
        else:
            # OpenRouter fallback: use a conservative estimate
            # Most OpenRouter models are cheaper than Claude, so use Haiku pricing as estimate
            input_cost_per_1m = CLAUDE_HAIKU_INPUT_COST
            output_cost_per_1m = CLAUDE_HAIKU_OUTPUT_COST
            cost = (input_tokens / 1_000_000 * input_cost_per_1m) + (
                output_tokens / 1_000_000 * output_cost_per_1m
            )
            return round(cost, 6)

    def _validate_schema(self, data: dict) -> ExtractionResult:
        """Validate LLM response against expected schema using Pydantic."""
        try:
            # Validate entities
            entities = [Entity(**raw) for raw in data.get("entities", [])]

            # Validate relationships
            relationships = [Relationship(**raw) for raw in data.get("relationships", [])]

            # Validate insights (simple list of strings)
            insights = data.get("insights", [])
            if not isinstance(insights, list) or not all(
                isinstance(i, str) for i in insights
            ):
                raise ValueError("Insights must be a list of strings")

            return ExtractionResult(
                entities=entities,
                relationships=relationships,
                insights=insights,
                estimated_cost_usd=0.0,  # Will be set by caller
            )
        except (ValidationError, KeyError, TypeError, ValueError) as exc:
            logger.error(
                "Schema validation failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            # Re-raise ValidationError as-is, wrap others in ValueError
            if isinstance(exc, ValidationError):
                raise
            raise ValueError(f"Invalid extraction schema: {exc}")

    def _call_llm_with_retry(
        self, session: ParsedSession, max_retries: int = 3
    ) -> ExtractionResult:
        """Call LLM with exponential backoff retry logic and chunking for large sessions."""
        # Estimate total session tokens
        total_text = "".join(msg.text for msg in session.messages)
        total_tokens = self._estimate_tokens(total_text)

        # Check if chunking is needed (>12K tokens)
        if total_tokens > 12000:
            logger.info(
                "Session exceeds token limit, splitting into chunks",
                session_id=session.metadata.session_id,
                total_tokens=total_tokens,
                chunk_threshold=12000,
            )
            return self._extract_with_chunking(session)

        # Standard extraction with retry for smaller sessions
        last_exception = None

        for attempt in range(max_retries):
            try:
                return self._call_llm(session)
            except (APIError, Exception) as exc:
                last_exception = exc
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2**attempt
                    logger.warning(
                        "LLM API error, retrying with exponential backoff",
                        session_id=session.metadata.session_id,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        wait_time_seconds=wait_time,
                        error=str(exc),
                        error_type=type(exc).__name__,
                        provider=self.provider,
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        "LLM API error after max retries, falling back to heuristics",
                        session_id=session.metadata.session_id,
                        max_retries=max_retries,
                        error=str(exc),
                        error_type=type(exc).__name__,
                        provider=self.provider,
                    )
                    raise

        raise last_exception  # Should never reach here, but satisfy type checker

    def _extract_with_chunking(self, session: ParsedSession) -> ExtractionResult:
        """Extract from large session by processing chunks and merging results."""
        chunks = self._chunk_session(session)
        logger.info(
            "Processing session with chunking",
            session_id=session.metadata.session_id,
            num_chunks=len(chunks),
        )

        chunk_results: list[ExtractionResult] = []

        for i, chunk_messages in enumerate(chunks):
            # Create a temporary session for this chunk
            chunk_session = ParsedSession(
                metadata=session.metadata,
                messages=chunk_messages,
                total_tokens=sum(
                    self._estimate_tokens(msg.text) for msg in chunk_messages
                ),
                referenced_files=session.referenced_files,
            )

            logger.debug(
                "Processing chunk",
                session_id=session.metadata.session_id,
                chunk_index=i + 1,
                total_chunks=len(chunks),
            )

            # Extract from this chunk (with retry logic)
            chunk_result = self._call_llm(chunk_session)
            chunk_results.append(chunk_result)

        # Merge all chunk results
        merged_result = self._merge_extractions(chunk_results)
        logger.info(
            "Merged chunk results",
            session_id=session.metadata.session_id,
            num_chunks=len(chunks),
            entities_created=len(merged_result.entities),
            relationships_created=len(merged_result.relationships),
            total_cost_usd=merged_result.estimated_cost_usd,
        )

        return merged_result

    def _estimate_session_cost(self, session: ParsedSession) -> float:
        """Estimate cost for a session based on token count."""
        # Rough estimate: 4 chars per token
        prompt = self._build_prompt(session)
        estimated_input_tokens = len(prompt) // 4
        estimated_output_tokens = 1024  # Max tokens we request

        return self._calculate_cost(estimated_input_tokens, estimated_output_tokens)

    def _call_llm(self, session: ParsedSession) -> ExtractionResult:
        """Route to appropriate provider's LLM call method."""
        if self.provider == "anthropic":
            return self._call_anthropic(session)
        elif self.provider == "openrouter":
            return self._call_litellm(session)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _call_anthropic(self, session: ParsedSession) -> ExtractionResult:
        """Call Anthropic API for extraction."""
        # Check cost limit before making API call
        if self.cost_guard:
            estimated_cost = self._estimate_session_cost(session)
            if not self.cost_guard.check_session(estimated_cost):
                logger.warning(
                    "Session cost exceeds limit, falling back to heuristics",
                    session_id=session.metadata.session_id,
                    estimated_cost_usd=estimated_cost,
                    max_cost_usd=self.cost_guard.max_session,
                )
                raise CostLimitExceeded(
                    f"Estimated session cost ${estimated_cost:.6f} exceeds limit "
                    f"${self.cost_guard.max_session:.2f}",
                    current_cost=estimated_cost,
                    limit=self.cost_guard.max_session,
                    limit_type="session",
                )

        if not self.client:
            raise ValueError("Anthropic client not initialized")

        prompt = self._build_prompt(session)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0,
            system="Return valid JSON only; no commentary.",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        # Extract actual token usage from response
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        # Calculate actual cost based on usage
        actual_cost = self._calculate_cost(input_tokens, output_tokens)

        # Record cost metrics
        if self.metrics:
            self.metrics.record_cost(actual_cost, self.model, "api_call")

        logger.debug(
            "Anthropic extraction completed",
            session_id=session.metadata.session_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=actual_cost,
            model=self.model,
        )

        # Record actual cost with cost guard
        if self.cost_guard:
            self.cost_guard.record(actual_cost)

        text = "\n".join(block.text for block in response.content if block.type == "text").strip()
        data = json.loads(text)

        # Validate schema before accepting
        result = self._validate_schema(data)

        # Update with actual cost and provenance
        result.estimated_cost_usd = actual_cost
        result.extracted_at = datetime.now(tz=timezone.utc).isoformat()
        result.extractor_model = self.model
        result.extraction_method = "llm"

        return result

    def _call_litellm(self, session: ParsedSession) -> ExtractionResult:
        """Call OpenRouter API via LiteLLM for extraction."""
        # Check cost limit before making API call
        if self.cost_guard:
            estimated_cost = self._estimate_session_cost(session)
            if not self.cost_guard.check_session(estimated_cost):
                logger.warning(
                    "Session cost exceeds limit, falling back to heuristics",
                    session_id=session.metadata.session_id,
                    estimated_cost_usd=estimated_cost,
                    max_cost_usd=self.cost_guard.max_session,
                )
                raise CostLimitExceeded(
                    f"Estimated session cost ${estimated_cost:.6f} exceeds limit "
                    f"${self.cost_guard.max_session:.2f}",
                    current_cost=estimated_cost,
                    limit=self.cost_guard.max_session,
                    limit_type="session",
                )

        if not self.openrouter_api_key:
            raise ValueError("OpenRouter API key not initialized")

        prompt = self._build_prompt(session)

        # Use LiteLLM to call OpenRouter
        # Model format: can be "x-ai/grok-4.1-fast" or "openrouter/x-ai/grok-4.1-fast"
        model_name = self.model
        if not model_name.startswith("openrouter/"):
            model_name = f"openrouter/{model_name}"

        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            api_key=self.openrouter_api_key,
            base_url=self.openrouter_base_url,
            max_tokens=1024,
            temperature=0,
        )

        # Extract response text
        text = response.choices[0].message.content.strip()

        # Extract token usage
        input_tokens = getattr(response.usage, "prompt_tokens", 0) if hasattr(response, "usage") else 0
        output_tokens = (
            getattr(response.usage, "completion_tokens", 0) if hasattr(response, "usage") else 0
        )

        # Calculate cost using LiteLLM's cost tracking
        actual_cost = self._calculate_cost(input_tokens, output_tokens, response=response)

        # Record cost metrics
        if self.metrics:
            self.metrics.record_cost(actual_cost, self.model, "api_call")

        logger.debug(
            "OpenRouter extraction completed",
            session_id=session.metadata.session_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=actual_cost,
            model=self.model,
        )

        # Record actual cost with cost guard
        if self.cost_guard:
            self.cost_guard.record(actual_cost)

        # Parse JSON response
        data = json.loads(text)

        # Validate schema before accepting
        result = self._validate_schema(data)

        # Update with actual cost and provenance
        result.estimated_cost_usd = actual_cost
        result.extracted_at = datetime.now(tz=timezone.utc).isoformat()
        result.extractor_model = self.model
        result.extraction_method = "llm"

        return result

    def _build_prompt(self, session: ParsedSession) -> str:
        snippets = []
        for message in session.messages[-10:]:
            snippets.append(f"{message.role.upper()}: {message.text[:400]}")
        joined = "\n\n".join(snippets)
        return (
            "Extract structured knowledge from the following Claude Code session.\n"
            "Return JSON with keys: entities (list of {type,name,metadata}), "
            "relationships (list of {type,source,target,metadata}), "
            "insights (list of short strings), estimated_cost_usd (number).\n"
            f"Session snippets:\n{joined}"
        )

    def _heuristic_extract(self, session: ParsedSession) -> ExtractionResult:
        entities: list[Entity] = []
        insights: list[str] = []
        seen_files: set[str] = set()

        # Add files from session.referenced_files (from parser)
        for file_path in session.referenced_files:
            if file_path not in seen_files:
                seen_files.add(file_path)
                entities.append(
                    Entity(
                        type="file",
                        name=file_path,
                        confidence=1.0,  # High confidence for file paths from session data
                        metadata={"project": session.metadata.project},
                    )
                )

        # Extract file paths from message text using regex
        # Pattern matches absolute paths like /Users/... or /home/... or relative paths with extensions
        file_path_pattern = re.compile(
            r'(?:^|[\s"\':,\(\[])(/(?:Users|home|var|etc|opt|tmp)[^\s"\',:;\)\]\n]+\.[a-zA-Z0-9]+)|'
            r'(?:file_path["\']?\s*:\s*["\']?)([^\s"\',:;\)\]\n]+\.[a-zA-Z0-9]+)'
        )

        for msg in session.messages:
            if not msg.text:
                continue
            matches = file_path_pattern.findall(msg.text)
            for match_groups in matches:
                # match_groups is a tuple of groups, get first non-empty
                file_path = next((g for g in match_groups if g), None)
                if file_path and file_path not in seen_files:
                    # Filter out common non-file patterns
                    if not any(x in file_path.lower() for x in ['.com/', '.org/', '.io/', 'http']):
                        seen_files.add(file_path)
                        entities.append(
                            Entity(
                                type="file",
                                name=file_path,
                                confidence=0.8,  # Medium-high confidence for regex-extracted paths
                                metadata={"project": session.metadata.project, "source": "text_extraction"},
                            )
                        )

        if session.total_tokens:
            insights.append(
                f"Session {session.metadata.session_id} used {session.total_tokens} tokens."
            )

        # Add insight about file count
        if len(entities) > 0:
            insights.append(
                f"Session referenced {len(entities)} unique files."
            )

        return ExtractionResult(
            entities=entities,
            relationships=[],
            insights=insights,
            estimated_cost_usd=0.0,
            extracted_at=datetime.now(tz=timezone.utc).isoformat(),
            extractor_model="heuristic",
            extraction_method="heuristic",
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation: 4 chars per token)."""
        return len(text) // 4

    def _chunk_session(
        self, session: ParsedSession, max_tokens: int = 12000
    ) -> list[list[SessionMessage]]:
        """Split large session into overlapping chunks.

        Returns list of message chunks, each with 2-message overlap for context.
        """
        chunks: list[list[SessionMessage]] = []
        current_chunk: list[SessionMessage] = []
        current_tokens = 0

        for i, message in enumerate(session.messages):
            message_tokens = self._estimate_tokens(message.text)

            # If adding this message would exceed the limit, start a new chunk
            if current_chunk and current_tokens + message_tokens > max_tokens:
                chunks.append(current_chunk)

                # Start new chunk with last 2 messages for overlap
                overlap_size = min(2, len(current_chunk))
                current_chunk = current_chunk[-overlap_size:]
                current_tokens = sum(
                    self._estimate_tokens(msg.text) for msg in current_chunk
                )

            current_chunk.append(message)
            current_tokens += message_tokens

        # Add the last chunk if it has content
        if current_chunk:
            chunks.append(current_chunk)

        # If no chunking needed (session fits in one chunk), return as single chunk
        return chunks if len(chunks) > 1 else [session.messages]

    def _format_chunk(self, messages: list[SessionMessage]) -> str:
        """Format a chunk of messages as a string for LLM prompt."""
        snippets = []
        # Take up to last 10 messages to keep prompt size manageable
        for message in messages[-10:]:
            snippets.append(f"{message.role.upper()}: {message.text[:400]}")
        joined = "\n\n".join(snippets)
        return (
            "Extract structured knowledge from the following Claude Code session.\n"
            "Return JSON with keys: entities (list of {type,name,metadata}), "
            "relationships (list of {type,source,target,metadata}), "
            "insights (list of short strings), estimated_cost_usd (number).\n"
            f"Session snippets:\n{joined}"
        )

    def _merge_extractions(
        self, results: list[ExtractionResult]
    ) -> ExtractionResult:
        """Merge and deduplicate entities from multiple chunks."""
        if not results:
            return ExtractionResult()

        # Use dictionaries to deduplicate by key
        entities_dict: dict[tuple[str, str], Entity] = {}
        relationships_dict: dict[tuple[str, str, str], Relationship] = {}
        all_insights: list[str] = []
        total_cost = 0.0

        for result in results:
            # Deduplicate entities by (type, name)
            for entity in result.entities:
                key = (entity.type, entity.name)
                if key not in entities_dict:
                    entities_dict[key] = entity
                else:
                    # Keep entity with higher confidence
                    if entity.confidence > entities_dict[key].confidence:
                        entities_dict[key] = entity

            # Deduplicate relationships by (source, target, type)
            for rel in result.relationships:
                key = (rel.source, rel.target, rel.type)
                if key not in relationships_dict:
                    relationships_dict[key] = rel
                else:
                    # Keep relationship with higher confidence
                    if rel.confidence > relationships_dict[key].confidence:
                        relationships_dict[key] = rel

            # Collect all insights (deduplicate at list level)
            all_insights.extend(result.insights)

            # Sum costs
            total_cost += result.estimated_cost_usd

        # Deduplicate insights
        unique_insights = list(dict.fromkeys(all_insights))

        # Take metadata from first result
        first_result = results[0]

        return ExtractionResult(
            entities=list(entities_dict.values()),
            relationships=list(relationships_dict.values()),
            insights=unique_insights,
            estimated_cost_usd=total_cost,
            extracted_at=first_result.extracted_at,
            extractor_model=first_result.extractor_model,
            extraction_method=first_result.extraction_method,
        )
