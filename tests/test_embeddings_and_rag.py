"""Tests for embeddings and RAG services."""
import pytest
from unittest.mock import Mock, patch

from storage.embeddings import EmbeddingService
from storage.rag import RAGService
from storage.schemas import CommitmentChunk


class TestEmbeddingService:
    """Tests for embedding service."""

    @patch('storage.embeddings.SentenceTransformer')
    def test_embed_text(self, mock_transformer):
        """Test embedding a single text."""
        import numpy as np

        # Mock the embedding model
        mock_model = Mock()
        mock_model.encode.return_value = np.array([0.1] * 384)
        mock_transformer.return_value = mock_model

        service = EmbeddingService()
        embedding = service.embed_text("test text")

        assert len(embedding) == 384
        mock_model.encode.assert_called_once()

    @patch('storage.embeddings.SentenceTransformer')
    def test_embed_texts(self, mock_transformer):
        """Test embedding multiple texts."""
        import numpy as np

        mock_model = Mock()
        mock_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384])
        mock_transformer.return_value = mock_model

        service = EmbeddingService()
        embeddings = service.embed_texts(["text1", "text2"])

        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        service = EmbeddingService()

        # Identical vectors should have similarity of 1.0
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = service.cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.001

        # Orthogonal vectors should have similarity of 0.0
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = service.cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 0.001

        # Opposite vectors should have similarity of -1.0
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = service.cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 0.001

    def test_find_most_similar(self):
        """Test finding most similar embeddings."""
        service = EmbeddingService()

        query = [1.0, 0.0, 0.0]
        candidates = [
            [1.0, 0.0, 0.0],  # Identical
            [0.9, 0.1, 0.0],  # Very similar
            [0.0, 1.0, 0.0],  # Orthogonal
            [-1.0, 0.0, 0.0], # Opposite
        ]

        results = service.find_most_similar(query, candidates, top_k=2)

        # Should return indices of top 2 most similar
        assert len(results) == 2
        assert results[0][0] == 0  # First result is index 0 (identical)
        assert results[0][1] > 0.9  # High similarity

    def test_find_most_similar_with_threshold(self):
        """Test finding similar embeddings with threshold."""
        service = EmbeddingService()

        query = [1.0, 0.0, 0.0]
        candidates = [
            [1.0, 0.0, 0.0],  # similarity = 1.0
            [0.9, 0.1, 0.0],  # similarity ~= 0.99
            [0.5, 0.5, 0.0],  # similarity ~= 0.7
            [0.0, 1.0, 0.0],  # similarity = 0.0
        ]

        # Only results above threshold should be returned
        results = service.find_most_similar(query, candidates, top_k=10, threshold=0.9)

        assert len(results) <= 2  # Only first two above threshold


class TestRAGService:
    """Tests for RAG service."""

    def test_chunk_text(self):
        """Test text chunking."""
        service = RAGService()
        service.chunk_size = 100
        service.chunk_overlap = 20

        text = "a" * 250  # 250 character text

        chunks = service.chunk_text(text)

        # Should create multiple chunks
        assert len(chunks) > 1

        # Each chunk should be approximately chunk_size
        for chunk in chunks[:-1]:  # Exclude last chunk
            assert len(chunk) == 100

    def test_chunk_text_no_tiny_chunks(self):
        """Test that tiny chunks at the end are excluded."""
        service = RAGService()
        service.chunk_size = 100
        service.chunk_overlap = 20

        text = "a" * 110  # Just slightly more than chunk_size

        chunks = service.chunk_text(text)

        # Should not create tiny chunks
        assert all(len(chunk) > 50 for chunk in chunks)

    @patch('storage.rag.db')
    @patch('storage.rag.embedding_service')
    def test_process_and_store_commitment(self, mock_embed_service, mock_db, temp_db, sample_commitment):
        """Test processing and storing commitment."""
        # Mock embedding service
        mock_embed_service.embed_texts.return_value = [[0.1] * 384, [0.2] * 384]

        # Mock db to use temp_db
        mock_db.add_commitment_chunks = temp_db.add_commitment_chunks
        mock_db.get_commitment_chunks = temp_db.get_commitment_chunks

        service = RAGService()
        service.chunk_size = 100
        service.chunk_overlap = 20

        # Add commitment to DB first
        temp_db.add_commitment(sample_commitment)

        # Process and store
        chunks = service.process_and_store_commitment(sample_commitment)

        # Should create chunks
        assert len(chunks) > 0

        # Chunks should be stored
        stored_chunks = temp_db.get_commitment_chunks(sample_commitment.id)
        assert len(stored_chunks) == len(chunks)

    @patch('storage.rag.embedding_service')
    def test_retrieve_relevant_chunks(self, mock_embed_service, temp_db, sample_commitment, mock_embedding):
        """Test retrieving relevant chunks."""
        # Setup
        temp_db.add_commitment(sample_commitment)

        chunks = [
            CommitmentChunk(
                commitment_id=sample_commitment.id,
                chunk_text="Production databases need controls",
                chunk_embedding=[1.0] + [0.0] * 383,
                chunk_index=0
            ),
            CommitmentChunk(
                commitment_id=sample_commitment.id,
                chunk_text="Test environments are excluded",
                chunk_embedding=[0.0] + [1.0] + [0.0] * 382,
                chunk_index=1
            )
        ]

        temp_db.add_commitment_chunks(chunks)

        # Mock similarity calculations to return deterministic results
        mock_embed_service.find_most_similar.return_value = [(0, 0.95), (1, 0.75)]

        service = RAGService()
        service.top_k = 2

        query_embedding = [1.0] + [0.0] * 383

        retrieved_chunks, scores = service.retrieve_relevant_chunks(
            query_embedding=query_embedding,
            commitment_id=sample_commitment.id
        )

        # Should retrieve chunks
        assert len(retrieved_chunks) <= 2
        assert len(scores) == len(retrieved_chunks)

    @patch('storage.rag.embedding_service')
    def test_get_commitment_context(self, mock_embed_service, temp_db, sample_commitment, mock_embedding):
        """Test getting commitment context."""
        temp_db.add_commitment(sample_commitment)

        chunks = [
            CommitmentChunk(
                commitment_id=sample_commitment.id,
                chunk_text="Test chunk",
                chunk_embedding=mock_embedding,
                chunk_index=0
            )
        ]

        temp_db.add_commitment_chunks(chunks)

        # Mock retrieval
        mock_embed_service.find_most_similar.return_value = [(0, 0.95)]

        service = RAGService()

        context = service.get_commitment_context(
            query_embedding=mock_embedding,
            commitment_id=sample_commitment.id
        )

        # Should return context with metadata
        assert "chunks" in context
        assert "scores" in context
        assert "avg_similarity" in context
        assert "top_similarity" in context
        assert context["num_chunks"] >= 0
