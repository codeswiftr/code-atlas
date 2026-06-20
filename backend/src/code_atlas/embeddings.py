"""Embedding generation for entity semantic search.

Provides functionality to generate embeddings for entities using sentence-transformers,
enabling semantic similarity search over the knowledge graph.
"""

from __future__ import annotations

import numpy as np

from .logging_config import get_logger

logger = get_logger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment, misc]


class EmbeddingGenerator:
    """Generates embeddings for entities using sentence-transformers."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: str | None = None,
    ) -> None:
        """Initialize embedding generator with a sentence-transformers model.

        Args:
            model_name: Name of the sentence-transformers model to use.
                Defaults to 'all-MiniLM-L6-v2' for speed.
                Alternatives: 'all-mpnet-base-v2' for quality.
            cache_dir: Directory to cache model files. None uses default cache.
        """
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it with: uv add sentence-transformers"
            )

        logger.info("Loading embedding model", model=model_name)
        self.model = SentenceTransformer(model_name, cache_folder=cache_dir)
        self.model_name = model_name
        self.embedding_dim = self.model.get_sentence_embedding_dimension() or 0
        logger.info(
            "Embedding model loaded",
            model=model_name,
            embedding_dim=self.embedding_dim,
        )

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for a single text.

        Args:
            text: Text to embed (entity name, description, etc.)

        Returns:
            List of floats representing the embedding vector.
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.embedding_dim

        embedding = self.model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return embedding.tolist()

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors (one per input text).
        """
        if not texts:
            return []

        # Filter empty texts
        non_empty_texts = [t.strip() if t else "" for t in texts]
        valid_indices = [i for i, t in enumerate(non_empty_texts) if t]

        if not valid_indices:
            # All texts are empty, return zero vectors
            return [[0.0] * self.embedding_dim for _ in texts]

        # Generate embeddings only for valid texts
        valid_texts = [non_empty_texts[i] for i in valid_indices]
        embeddings = self.model.encode(
            valid_texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )

        # Build full result list with zero vectors for empty texts
        result: list[list[float]] = []
        valid_idx = 0
        for i in range(len(texts)):
            if i in valid_indices:
                result.append(embeddings[valid_idx].tolist())
                valid_idx += 1
            else:
                result.append([0.0] * self.embedding_dim)

        return result

    def calculate_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if len(embedding1) != len(embedding2):
            logger.warning(
                "Embedding dimension mismatch",
                dim1=len(embedding1),
                dim2=len(embedding2),
            )
            return 0.0

        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Cosine similarity: dot product of normalized vectors
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        # Clamp to [0, 1] range (should already be there for normalized embeddings)
        return max(0.0, min(1.0, float(similarity)))


def get_embedding_generator(
    model_name: str | None = None,
    cache_dir: str | None = None,
) -> EmbeddingGenerator:
    """Get or create a cached embedding generator instance.

    Args:
        model_name: Model name to use. None uses default.
        cache_dir: Cache directory for model files.

    Returns:
        EmbeddingGenerator instance.
    """
    # Simple singleton pattern - can be enhanced with proper caching later
    if not hasattr(get_embedding_generator, "_instance"):
        get_embedding_generator._instance = EmbeddingGenerator(  # type: ignore[attr-defined]
            model_name=model_name or "all-MiniLM-L6-v2",
            cache_dir=cache_dir,
        )
    return get_embedding_generator._instance  # type: ignore[attr-defined]
