"""Pydantic schemas for embedding-related API requests and responses."""


from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    """Request to generate embeddings for text."""

    text: str = Field(..., min_length=1, max_length=1000, description="Text to embed")
    normalize: bool = Field(default=True, description="Normalize embedding vector")


class EmbeddingResponse(BaseModel):
    """Response containing generated embedding."""

    embedding: list[float] = Field(..., description="Embedding vector")
    dimension: int = Field(..., description="Dimension of embedding vector")
    model: str = Field(..., description="Model used for generation")


class BatchEmbeddingRequest(BaseModel):
    """Request to generate embeddings for multiple texts."""

    texts: list[str] = Field(..., min_length=1, max_length=100, description="Texts to embed")
    normalize: bool = Field(default=True, description="Normalize embedding vectors")


class BatchEmbeddingResponse(BaseModel):
    """Response containing multiple embeddings."""

    embeddings: list[list[float]] = Field(..., description="List of embedding vectors")
    dimension: int = Field(..., description="Dimension of each embedding vector")
    model: str = Field(..., description="Model used for generation")
    count: int = Field(..., description="Number of embeddings generated")


class SimilarityRequest(BaseModel):
    """Request to calculate similarity between embeddings."""

    embedding1: list[float] = Field(..., description="First embedding vector")
    embedding2: list[float] = Field(..., description="Second embedding vector")


class SimilarityResponse(BaseModel):
    """Response containing similarity score."""

    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    embedding1_dim: int = Field(..., description="Dimension of first embedding")
    embedding2_dim: int = Field(..., description="Dimension of second embedding")
