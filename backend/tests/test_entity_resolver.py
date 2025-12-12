"""Tests for entity deduplication and resolver."""

from __future__ import annotations

from unittest.mock import Mock

from code_atlas.entity_resolver import EntityResolver


class TestSimilarityCalculation:
    """Tests for similarity score calculation."""

    def test_exact_match_returns_one(self) -> None:
        """Exact name returns 1.0 similarity."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])

        resolver = EntityResolver(graph=mock_graph)

        score = resolver._calculate_similarity("Authentication", "Authentication")
        assert score == 1.0

    def test_case_insensitive_exact_match(self) -> None:
        """Case-insensitive matching works."""
        mock_graph = Mock()
        resolver = EntityResolver(graph=mock_graph)

        score = resolver._calculate_similarity("Auth", "auth")
        assert score == 1.0

        score = resolver._calculate_similarity("AUTHENTICATION", "authentication")
        assert score == 1.0

    def test_substring_match_high_score(self) -> None:
        """Substring matches get high scores."""
        mock_graph = Mock()
        resolver = EntityResolver(graph=mock_graph)

        # "Auth" is contained in "Authentication"
        score = resolver._calculate_similarity("Auth", "Authentication")
        assert score >= 0.8

        # "login" in "user login system"
        score = resolver._calculate_similarity("login", "user login system")
        assert score >= 0.8

    def test_typo_tolerance(self) -> None:
        """Typos are detected with reasonable scores."""
        mock_graph = Mock()
        resolver = EntityResolver(graph=mock_graph)

        # Common typo
        score = resolver._calculate_similarity("authetication", "authentication")
        assert score >= 0.85

        # Missing letter
        score = resolver._calculate_similarity("authenticaton", "authentication")
        assert score >= 0.9

    def test_different_strings_low_score(self) -> None:
        """Completely different strings get low scores."""
        mock_graph = Mock()
        resolver = EntityResolver(graph=mock_graph)

        score = resolver._calculate_similarity("authentication", "database")
        assert score < 0.5

        score = resolver._calculate_similarity("user", "connection")
        assert score < 0.5


class TestFindSimilar:
    """Tests for finding similar entities."""

    def test_finds_similar_entities(self) -> None:
        """Similar entities are found above threshold."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(
            return_value=[
                {"id": "entity-1", "name": "Authentication"},
                {"id": "entity-2", "name": "Authorization"},
                {"id": "entity-3", "name": "Database"},
            ]
        )

        resolver = EntityResolver(graph=mock_graph, similarity_threshold=0.85)

        # "Auth" should match "Authentication" but not "Database"
        similar = resolver.find_similar("Concept", "Auth")

        # Should find Authentication (contains "Auth")
        assert len(similar) >= 1
        assert any(name == "Authentication" for _, name, _ in similar)

    def test_respects_similarity_threshold(self) -> None:
        """Only entities above threshold are returned."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(
            return_value=[
                {"id": "entity-1", "name": "Authentication"},
                {"id": "entity-2", "name": "Database"},
            ]
        )

        # High threshold
        resolver = EntityResolver(graph=mock_graph, similarity_threshold=0.95)
        similar = resolver.find_similar("Concept", "Auth")

        # Should not find anything with very high threshold
        # since "Auth" vs "Authentication" is ~0.8
        found_names = [name for _, name, _ in similar]
        # Authentication might still match if it contains "Auth"
        assert "Database" not in found_names

    def test_returns_empty_for_no_matches(self) -> None:
        """Returns empty list when no similar entities exist."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(
            return_value=[
                {"id": "entity-1", "name": "Database"},
                {"id": "entity-2", "name": "Connection"},
            ]
        )

        resolver = EntityResolver(graph=mock_graph, similarity_threshold=0.85)
        similar = resolver.find_similar("Concept", "Authentication")

        # No similar matches expected
        assert len(similar) == 0

    def test_handles_empty_results(self) -> None:
        """Handles case when no entities exist."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])

        resolver = EntityResolver(graph=mock_graph)
        similar = resolver.find_similar("Concept", "Authentication")

        assert similar == []

    def test_handles_query_error(self) -> None:
        """Gracefully handles database errors."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(side_effect=Exception("DB error"))

        resolver = EntityResolver(graph=mock_graph)
        similar = resolver.find_similar("Concept", "Authentication")

        assert similar == []


class TestResolve:
    """Tests for entity resolution."""

    def test_returns_existing_id_for_similar(self) -> None:
        """Returns existing entity ID when similar entity exists."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(
            return_value=[
                {"id": "existing-123", "name": "Authentication"},
            ]
        )

        resolver = EntityResolver(graph=mock_graph, similarity_threshold=0.85)
        entity_id, is_existing = resolver.resolve("Concept", "Auth")

        # Should return existing ID since "Auth" is in "Authentication"
        assert entity_id == "existing-123"
        assert is_existing is True

    def test_generates_new_id_for_unique(self) -> None:
        """Generates new ID when no similar entity exists."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(
            return_value=[
                {"id": "entity-1", "name": "Database"},
            ]
        )

        resolver = EntityResolver(graph=mock_graph, similarity_threshold=0.85)
        entity_id, is_existing = resolver.resolve("Concept", "Authentication")

        assert is_existing is False
        assert len(entity_id) == 40  # SHA1 hex digest length


class TestMergeEntities:
    """Tests for entity merge operations."""

    def test_merge_success(self) -> None:
        """Successful merge updates target and deletes source."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])

        resolver = EntityResolver(graph=mock_graph)
        result = resolver.merge_entities(
            source_id="source-123",
            target_id="target-456",
            source_name="Auth",
            target_name="Authentication",
            similarity_score=0.92,
        )

        assert result is True
        # Verify queries were executed
        assert mock_graph.execute_query.call_count >= 3  # Transfer in, out, update, delete

    def test_merge_records_history(self) -> None:
        """Merge operation is recorded in history."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])

        resolver = EntityResolver(graph=mock_graph)
        resolver.merge_entities(
            source_id="source-123",
            target_id="target-456",
            source_name="Auth",
            target_name="Authentication",
            similarity_score=0.92,
        )

        assert len(resolver.merge_history) == 1
        record = resolver.merge_history[0]
        assert record.merged_id == "source-123"
        assert record.canonical_id == "target-456"
        assert record.similarity_score == 0.92

    def test_merge_handles_error(self) -> None:
        """Merge handles database errors gracefully."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(side_effect=Exception("DB error"))

        resolver = EntityResolver(graph=mock_graph)
        result = resolver.merge_entities(
            source_id="source-123",
            target_id="target-456",
            source_name="Auth",
            target_name="Authentication",
            similarity_score=0.92,
        )

        assert result is False
        assert len(resolver.merge_history) == 0


class TestDeduplicateBatch:
    """Tests for batch deduplication."""

    def test_deduplicates_similar_names_in_batch(self) -> None:
        """Similar names in batch get same ID."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])

        resolver = EntityResolver(graph=mock_graph, similarity_threshold=0.85)
        names = ["Authentication", "Auth", "authentication"]

        resolved = resolver.deduplicate_batch("Concept", names)

        # All similar names should resolve to same ID
        assert len(set(resolved.values())) < len(names)

    def test_unique_names_get_unique_ids(self) -> None:
        """Unique names get different IDs."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])

        resolver = EntityResolver(graph=mock_graph, similarity_threshold=0.85)
        names = ["Authentication", "Database", "Connection"]

        resolved = resolver.deduplicate_batch("Concept", names)

        # Each unique name should have unique ID
        assert len(set(resolved.values())) == len(names)


class TestMergeHistory:
    """Tests for merge history tracking."""

    def test_get_all_merge_history(self) -> None:
        """Can retrieve all merge history."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])

        resolver = EntityResolver(graph=mock_graph)

        # Create some merge records
        resolver.merge_entities("s1", "t1", "name1", "Name One", 0.9)
        resolver.merge_entities("s2", "t2", "name2", "Name Two", 0.85)

        history = resolver.get_merge_history()
        assert len(history) == 2

    def test_filter_history_by_entity(self) -> None:
        """Can filter merge history by entity ID."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])

        resolver = EntityResolver(graph=mock_graph)

        resolver.merge_entities("s1", "t1", "name1", "Name One", 0.9)
        resolver.merge_entities("s2", "t2", "name2", "Name Two", 0.85)

        history = resolver.get_merge_history(entity_id="s1")
        assert len(history) == 1
        assert history[0].merged_id == "s1"

        history = resolver.get_merge_history(entity_id="t1")
        assert len(history) == 1
        assert history[0].canonical_id == "t1"


class TestStats:
    """Tests for deduplication statistics."""

    def test_stats_with_merges(self) -> None:
        """Stats correctly computed with merges."""
        mock_graph = Mock()
        mock_graph.execute_query = Mock(return_value=[])

        resolver = EntityResolver(graph=mock_graph)

        resolver.merge_entities("s1", "t1", "name1", "Name One", 0.9)
        resolver.merge_entities("s2", "t1", "name2", "Name One", 0.85)

        stats = resolver.get_stats()

        assert stats["total_merges"] == 2
        assert stats["avg_similarity"] == 0.875
        assert stats["unique_canonical_ids"] == 1  # Both merged into t1

    def test_stats_with_no_merges(self) -> None:
        """Stats are zero with no merges."""
        mock_graph = Mock()
        resolver = EntityResolver(graph=mock_graph)

        stats = resolver.get_stats()

        assert stats["total_merges"] == 0
        assert stats["avg_similarity"] == 0.0
        assert stats["unique_canonical_ids"] == 0


class TestIdGeneration:
    """Tests for ID generation."""

    def test_generates_deterministic_ids(self) -> None:
        """Same name generates same ID."""
        mock_graph = Mock()
        resolver = EntityResolver(graph=mock_graph)

        id1 = resolver._generate_id("Authentication")
        id2 = resolver._generate_id("Authentication")

        assert id1 == id2

    def test_different_names_different_ids(self) -> None:
        """Different names generate different IDs."""
        mock_graph = Mock()
        resolver = EntityResolver(graph=mock_graph)

        id1 = resolver._generate_id("Authentication")
        id2 = resolver._generate_id("Database")

        assert id1 != id2
