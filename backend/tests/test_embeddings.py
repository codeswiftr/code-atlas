"""Tests for embedding generation functionality."""

import pytest

from code_atlas.embeddings import EmbeddingGenerator, get_embedding_generator


class TestEmbeddingGenerator:
    """Tests for EmbeddingGenerator class."""

    def test_init_requires_sentence_transformers(self):
        """Test that EmbeddingGenerator requires sentence-transformers."""
        # This test will skip if sentence-transformers is not installed
        try:
            generator = EmbeddingGenerator()
            assert generator is not None
            assert generator.model_name == "all-MiniLM-L6-v2"
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    def test_generate_embedding_single_text(self):
        """Test generating embedding for a single text."""
        try:
            generator = EmbeddingGenerator()
            text = "authentication system"
            embedding = generator.generate_embedding(text)

            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, float) for x in embedding)
            assert generator.embedding_dim == len(embedding)
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    def test_generate_embedding_empty_text(self):
        """Test that empty text returns zero vector."""
        try:
            generator = EmbeddingGenerator()
            embedding = generator.generate_embedding("")

            assert isinstance(embedding, list)
            assert len(embedding) == generator.embedding_dim
            assert all(x == 0.0 for x in embedding)
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    def test_generate_embeddings_batch(self):
        """Test batch embedding generation."""
        try:
            generator = EmbeddingGenerator()
            texts = ["authentication", "authorization", "database"]
            embeddings = generator.generate_embeddings_batch(texts)

            assert len(embeddings) == len(texts)
            for embedding in embeddings:
                assert len(embedding) == generator.embedding_dim
                assert all(isinstance(x, float) for x in embedding)
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    def test_generate_embeddings_batch_empty(self):
        """Test batch generation with empty list."""
        try:
            generator = EmbeddingGenerator()
            embeddings = generator.generate_embeddings_batch([])
            assert embeddings == []
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    def test_calculate_similarity(self):
        """Test similarity calculation between embeddings."""
        try:
            generator = EmbeddingGenerator()
            text1 = "authentication"
            text2 = "authorization"
            text3 = "database"

            emb1 = generator.generate_embedding(text1)
            emb2 = generator.generate_embedding(text2)
            emb3 = generator.generate_embedding(text3)

            # Similar concepts should have higher similarity
            sim_12 = generator.calculate_similarity(emb1, emb2)
            sim_13 = generator.calculate_similarity(emb1, emb3)

            assert 0.0 <= sim_12 <= 1.0
            assert 0.0 <= sim_13 <= 1.0
            # Authentication and authorization are more similar than auth and database
            assert sim_12 > sim_13
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    def test_calculate_similarity_same_text(self):
        """Test that same text has similarity of 1.0."""
        try:
            generator = EmbeddingGenerator()
            text = "authentication"
            emb = generator.generate_embedding(text)

            similarity = generator.calculate_similarity(emb, emb)
            assert abs(similarity - 1.0) < 0.01  # Allow small floating point differences
        except ImportError:
            pytest.skip("sentence-transformers not installed")

    def test_calculate_similarity_dimension_mismatch(self):
        """Test handling of dimension mismatch."""
        try:
            generator = EmbeddingGenerator()
            emb1 = [1.0, 2.0, 3.0]
            emb2 = [1.0, 2.0]

            similarity = generator.calculate_similarity(emb1, emb2)
            assert similarity == 0.0
        except ImportError:
            pytest.skip("sentence-transformers not installed")


class TestGetEmbeddingGenerator:
    """Tests for get_embedding_generator singleton function."""

    def test_returns_singleton_instance(self):
        """Test that get_embedding_generator returns same instance."""
        try:
            gen1 = get_embedding_generator()
            gen2 = get_embedding_generator()

            assert gen1 is gen2
            assert gen1.model_name == gen2.model_name
        except ImportError:
            pytest.skip("sentence-transformers not installed")
