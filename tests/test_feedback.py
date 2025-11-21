"""Tests for feedback collection and processing."""
import pytest
from unittest.mock import Mock, patch

from feedback.collector import FeedbackCollector
from feedback.processor import FeedbackProcessor
from storage.schemas import ScopingDecision, DecisionFeedback


class TestFeedbackCollector:
    """Tests for feedback collector."""

    @patch('storage.vector_store.vector_store')
    @patch('feedback.collector.db')
    @patch('feedback.collector.embedding_service')
    def test_submit_feedback_thumbs_up(self, mock_embed, mock_db, mock_vector, mock_embedding):
        """Test submitting thumbs up feedback."""
        import json
        # Setup mocks
        mock_db.get_scoping_decision.return_value = {
            "id": "decision-1",
            "asset_uri": "asset://database.test.production",
            "commitment_id": "commitment-1",
            "decision": "in-scope",
            "response": '{"decision": "in-scope", "reasoning": "Test"}',
            "query_embedding": json.dumps(mock_embedding)
        }
        mock_embed.embed_text.return_value = mock_embedding

        collector = FeedbackCollector(vector_store=mock_vector)
        feedback = collector.submit_feedback(
            decision_id="decision-1",
            rating="up",
            human_reason="Correctly identified database scope"
        )

        assert feedback is not None
        assert feedback.decision_id == "decision-1"
        assert feedback.rating == "up"
        assert feedback.human_correction is None
        assert mock_db.add_feedback.called

    @patch('storage.vector_store.vector_store')
    @patch('feedback.collector.db')
    @patch('feedback.collector.embedding_service')
    def test_submit_feedback_thumbs_down(self, mock_embed, mock_db, mock_vector, mock_embedding):
        """Test submitting thumbs down feedback with correction."""
        import json
        mock_db.get_scoping_decision.return_value = {
            "id": "decision-1",
            "asset_uri": "asset://database.test.production",
            "commitment_id": "commitment-1",
            "decision": "in-scope",
            "response": '{"decision": "in-scope", "reasoning": "Test"}',
            "query_embedding": json.dumps(mock_embedding)
        }
        mock_embed.embed_text.return_value = mock_embedding

        collector = FeedbackCollector(vector_store=mock_vector)
        feedback = collector.submit_feedback(
            decision_id="decision-1",
            rating="down",
            human_reason="Database does not contain PII",
            human_correction="Should be out-of-scope because data is anonymized"
        )

        assert feedback is not None
        assert feedback.rating == "down"
        assert feedback.human_correction is not None
        assert "out-of-scope" in feedback.human_correction

    @patch('feedback.collector.db')
    def test_submit_feedback_decision_not_found(self, mock_db):
        """Test submitting feedback for nonexistent decision."""
        mock_db.get_scoping_decision.return_value = None

        collector = FeedbackCollector()

        with pytest.raises(ValueError, match="Decision not found"):
            collector.submit_feedback(
                decision_id="nonexistent",
                rating="up",
                human_reason="Test"
            )

    @patch('feedback.collector.db')
    @patch('feedback.collector.embedding_service')
    def test_submit_feedback_missing_correction(self, mock_embed, mock_db, mock_embedding):
        """Test that thumbs down requires correction."""
        import json
        mock_db.get_scoping_decision.return_value = {
            "id": "decision-1",
            "asset_uri": "asset://database.test.production",
            "commitment_id": "commitment-1",
            "decision": "in-scope",
            "response": '{"decision": "in-scope", "reasoning": "Test"}',
            "query_embedding": json.dumps(mock_embedding)
        }

        collector = FeedbackCollector()

        with pytest.raises(ValueError, match="requires.*correction"):
            collector.submit_feedback(
                decision_id="decision-1",
                rating="down",
                human_reason="Wrong decision"
                # Missing human_correction
            )


class TestFeedbackProcessor:
    """Tests for feedback processor."""

    @patch('feedback.processor.db')
    def test_retrieve_similar_feedback(self, mock_db, mock_embedding):
        """Test retrieving similar feedback."""
        from storage.vector_store.base import SimilarityResult
        from storage.schemas import DecisionFeedback

        # Create mock feedback objects
        feedback1 = DecisionFeedback(
            id="feedback-1",
            decision_id="decision-1",
            asset_uri="asset://database.customer.production",
            commitment_id="commitment-1",
            query_embedding=mock_embedding,
            agent_decision="in-scope",
            agent_reasoning="Test reasoning",
            rating="up",
            human_reason="Correct"
        )
        feedback2 = DecisionFeedback(
            id="feedback-2",
            decision_id="decision-2",
            asset_uri="asset://database.test.production",
            commitment_id="commitment-1",
            query_embedding=mock_embedding,
            agent_decision="out-of-scope",
            agent_reasoning="Test reasoning",
            rating="down",
            human_reason="Missing controls",
            human_correction="in-scope"
        )

        # Create mock vector store
        mock_vector = Mock()
        mock_vector.search.return_value = [
            SimilarityResult(id="feedback-1", text="", score=0.95, metadata={}),
            SimilarityResult(id="feedback-2", text="", score=0.85, metadata={})
        ]

        # Mock db.list_feedback
        mock_db.list_feedback.return_value = [feedback1, feedback2]

        processor = FeedbackProcessor(vector_store=mock_vector)
        results = processor.retrieve_similar_feedback(
            query_embedding=mock_embedding,
            commitment_id="commitment-1",
            top_k=2
        )

        assert len(results) == 2
        assert results[0]["similarity"] == 0.95
        assert "frequency_weight" in results[0]

    @patch('feedback.processor.db')
    def test_get_feedback_stats(self, mock_db, mock_embedding):
        """Test getting feedback statistics."""
        from storage.schemas import DecisionFeedback

        # Create mock feedback objects
        feedback1 = DecisionFeedback(
            id="fb-1", decision_id="d-1",
            asset_uri="asset://test", commitment_id="c-1",
            query_embedding=mock_embedding,
            agent_decision="in-scope", agent_reasoning="Test",
            rating="up", human_reason="Correct"
        )
        feedback2 = DecisionFeedback(
            id="fb-2", decision_id="d-2",
            asset_uri="asset://test", commitment_id="c-1",
            query_embedding=mock_embedding,
            agent_decision="in-scope", agent_reasoning="Test",
            rating="up", human_reason="Correct"
        )
        feedback3 = DecisionFeedback(
            id="fb-3", decision_id="d-3",
            asset_uri="asset://test", commitment_id="c-1",
            query_embedding=mock_embedding,
            agent_decision="out-of-scope", agent_reasoning="Test",
            rating="down", human_reason="Wrong", human_correction="in-scope"
        )

        mock_db.list_feedback.return_value = [feedback1, feedback2, feedback3]

        processor = FeedbackProcessor()
        stats = processor.get_feedback_stats("commitment-1")

        assert stats["total"] == 3
        assert stats["thumbs_up"] == 2
        assert stats["thumbs_down"] == 1
        assert stats["accuracy"] == pytest.approx(0.666, rel=0.01)

    @patch('feedback.processor.db')
    def test_get_feedback_stats_no_feedback(self, mock_db):
        """Test stats with no feedback."""
        mock_db.list_feedback.return_value = []

        processor = FeedbackProcessor()
        stats = processor.get_feedback_stats("commitment-1")

        assert stats["total"] == 0
        assert stats["thumbs_up"] == 0
        assert stats["thumbs_down"] == 0
        assert stats["accuracy"] == 0.0

    @patch('feedback.processor.db')
    @patch('feedback.processor.embedding_service')
    def test_cluster_similar_feedback(self, mock_embed, mock_db, mock_embedding):
        """Test clustering similar feedback."""
        from storage.schemas import DecisionFeedback

        # Create mock feedback objects
        feedback1 = DecisionFeedback(
            id="feedback-1", decision_id="d-1",
            asset_uri="asset://database.customer.production",
            commitment_id="commitment-1",
            query_embedding=mock_embedding,
            agent_decision="in-scope", agent_reasoning="Test",
            rating="up", human_reason="Correct"
        )
        feedback2 = DecisionFeedback(
            id="feedback-2", decision_id="d-2",
            asset_uri="asset://database.test.production",
            commitment_id="commitment-1",
            query_embedding=mock_embedding,
            agent_decision="in-scope", agent_reasoning="Test",
            rating="up", human_reason="Correct"
        )

        mock_db.list_feedback.return_value = [feedback1, feedback2]

        # Mock similarity to be high (same cluster)
        mock_embed.cosine_similarity.return_value = 0.92

        processor = FeedbackProcessor()
        clusters = processor.cluster_similar_feedback("commitment-1", threshold=0.85)

        # Should cluster similar feedback together
        assert len(clusters) >= 1
        # Each cluster should have feedback items
        for cluster in clusters:
            assert len(cluster) > 0

    @patch('feedback.processor.db')
    @patch('feedback.processor.embedding_service')
    def test_retrieve_similar_feedback_with_frequency_weight(self, mock_embed, mock_db, mock_embedding):
        """Test that frequency weighting boosts clustered feedback."""
        # Create feedback where some are very similar (should cluster)
        mock_db.list_feedback_by_commitment.return_value = [
            {
                "id": "feedback-1",
                "decision_id": "decision-1",
                "asset_uri": "asset://database.customer.production",
                "agent_decision": "in-scope",
                "rating": "up",
                "human_reason": "Correct",
                "feedback_embedding": [1.0] + [0.0] * 383,
                "timestamp": "2024-01-01T00:00:00"
            },
            {
                "id": "feedback-2",
                "decision_id": "decision-2",
                "asset_uri": "asset://database.customer2.production",
                "agent_decision": "in-scope",
                "rating": "up",
                "human_reason": "Correct",
                "feedback_embedding": [0.98] + [0.02] * 383,  # Very similar
                "timestamp": "2024-01-02T00:00:00"
            }
        ]
        mock_embed.find_most_similar.return_value = [(0, 0.95), (1, 0.94)]

        processor = FeedbackProcessor()
        results = processor.retrieve_similar_feedback(
            query_embedding=mock_embedding,
            commitment_id="commitment-1",
            top_k=2
        )

        # Both should have frequency_weight >= 1.0
        assert all(r["frequency_weight"] >= 1.0 for r in results)
