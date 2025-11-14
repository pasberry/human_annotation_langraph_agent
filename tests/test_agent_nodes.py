"""Tests for agent nodes."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from agent.nodes.parse_asset import parse_asset_node
from agent.nodes.retrieve_rag import retrieve_rag_node
from agent.nodes.retrieve_feedback import retrieve_feedback_node
from agent.nodes.assess_confidence import assess_confidence_node
from agent.nodes.build_prompt import build_prompt_node
from agent.nodes.llm_call import llm_call_node
from agent.nodes.save_decision import save_decision_node
from storage.schemas import (
    AgentState, AssetURI, Commitment, CommitmentChunk,
    RAGContext, FeedbackContext, ConfidenceAssessment,
    ScopingResponse, Evidence
)


class TestParseAssetNode:
    """Tests for parse_asset_node."""

    def test_parse_valid_asset(self):
        """Test parsing a valid asset URI."""
        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )

        result = parse_asset_node(state)

        assert result.asset is not None
        assert result.asset.asset_type == "database"
        assert result.asset.asset_descriptor == "customer_data"
        assert result.asset.asset_domain == "production"
        assert "parse_asset" in result.telemetry_data
        assert result.telemetry_data["parse_asset"]["asset_type"] == "database"

    def test_parse_invalid_asset(self):
        """Test parsing an invalid asset URI."""
        state = AgentState(
            asset_uri="invalid-uri",
            commitment_id="test-commitment"
        )

        result = parse_asset_node(state)

        assert result.asset is None
        assert len(result.errors) > 0
        assert "parse_asset" in result.telemetry_data
        assert "error" in result.telemetry_data["parse_asset"]


class TestRetrieveRAGNode:
    """Tests for retrieve_rag_node."""

    @patch('agent.nodes.retrieve_rag.db')
    @patch('agent.nodes.retrieve_rag.rag_service')
    @patch('agent.nodes.retrieve_rag.embedding_service')
    def test_retrieve_rag_success(self, mock_embed, mock_rag, mock_db, sample_commitment, mock_embedding):
        """Test successful RAG retrieval."""
        # Setup mocks
        mock_db.get_commitment_by_name.return_value = sample_commitment
        mock_embed.embed_text.return_value = mock_embedding
        mock_rag.get_commitment_context.return_value = {
            "chunks": ["Test chunk 1", "Test chunk 2"],
            "scores": [0.95, 0.85],
            "avg_similarity": 0.90,
            "top_similarity": 0.95,
            "num_chunks": 2
        }

        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.asset = AssetURI.from_uri(state.asset_uri)

        result = retrieve_rag_node(state)

        assert result.commitment is not None
        assert result.rag_context is not None
        assert len(result.rag_context.chunks) == 2
        assert result.rag_context.avg_similarity == 0.90
        assert "retrieve_rag" in result.telemetry_data

    @patch('agent.nodes.retrieve_rag.db')
    def test_retrieve_rag_commitment_not_found(self, mock_db):
        """Test RAG retrieval when commitment is not found."""
        mock_db.get_commitment_by_name.return_value = None

        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="nonexistent-commitment"
        )
        state.asset = AssetURI.from_uri(state.asset_uri)

        result = retrieve_rag_node(state)

        assert result.commitment is None
        assert len(result.errors) > 0
        assert "Commitment not found" in result.errors[0]


class TestRetrieveFeedbackNode:
    """Tests for retrieve_feedback_node."""

    @patch('agent.nodes.retrieve_feedback.feedback_processor')
    @patch('agent.nodes.retrieve_feedback.embedding_service')
    def test_retrieve_feedback_with_results(self, mock_embed, mock_feedback, mock_embedding, sample_commitment):
        """Test feedback retrieval with results."""
        # Setup mocks
        mock_embed.embed_text.return_value = mock_embedding
        mock_feedback.retrieve_similar_feedback.return_value = [
            {
                "feedback_id": "feedback-1",
                "asset_uri": "asset://database.test.production",
                "decision": "in-scope",
                "rating": "down",
                "human_reason": "Missing PII controls",
                "similarity": 0.92,
                "frequency_weight": 1.2
            }
        ]

        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.asset = AssetURI.from_uri(state.asset_uri)
        state.commitment = sample_commitment

        result = retrieve_feedback_node(state)

        assert result.feedback_context is not None
        assert len(result.feedback_context.similar_feedback) == 1
        assert result.feedback_context.similar_feedback[0]["rating"] == "down"
        assert "retrieve_feedback" in result.telemetry_data

    @patch('agent.nodes.retrieve_feedback.feedback_processor')
    @patch('agent.nodes.retrieve_feedback.embedding_service')
    def test_retrieve_feedback_no_results(self, mock_embed, mock_feedback, mock_embedding, sample_commitment):
        """Test feedback retrieval with no results."""
        mock_embed.embed_text.return_value = mock_embedding
        mock_feedback.retrieve_similar_feedback.return_value = []

        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.asset = AssetURI.from_uri(state.asset_uri)
        state.commitment = sample_commitment

        result = retrieve_feedback_node(state)

        assert result.feedback_context is not None
        assert len(result.feedback_context.similar_feedback) == 0


class TestAssessConfidenceNode:
    """Tests for assess_confidence_node."""

    def test_assess_confidence_high(self, sample_commitment):
        """Test high confidence assessment."""
        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.commitment = sample_commitment
        state.rag_context = RAGContext(
            chunks=["chunk1", "chunk2"],
            chunk_scores=[0.95, 0.90],
            avg_similarity=0.925,
            top_similarity=0.95,
            num_chunks=2
        )
        state.feedback_context = FeedbackContext(
            similar_feedback=[
                {"rating": "up", "similarity": 0.90},
                {"rating": "up", "similarity": 0.85}
            ]
        )

        result = assess_confidence_node(state)

        assert result.confidence is not None
        assert result.confidence.level == "high"
        assert result.confidence.score >= 0.85

    def test_assess_confidence_low(self, sample_commitment):
        """Test low confidence assessment."""
        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.commitment = sample_commitment
        state.rag_context = RAGContext(
            chunks=["chunk1"],
            chunk_scores=[0.60],
            avg_similarity=0.60,
            top_similarity=0.60,
            num_chunks=1
        )
        state.feedback_context = FeedbackContext(
            similar_feedback=[]
        )

        result = assess_confidence_node(state)

        assert result.confidence is not None
        assert result.confidence.level in ["low", "insufficient"]


class TestBuildPromptNode:
    """Tests for build_prompt_node."""

    def test_build_prompt_with_rag_and_feedback(self, sample_commitment):
        """Test building prompt with RAG and feedback context."""
        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.asset = AssetURI.from_uri(state.asset_uri)
        state.commitment = sample_commitment
        state.rag_context = RAGContext(
            chunks=["Production databases require controls"],
            chunk_scores=[0.95],
            avg_similarity=0.95,
            top_similarity=0.95,
            num_chunks=1
        )
        state.feedback_context = FeedbackContext(
            similar_feedback=[
                {"asset_uri": "asset://database.test.production", "decision": "in-scope", "rating": "up"}
            ]
        )
        state.confidence = ConfidenceAssessment(
            score=0.85,
            level="high",
            factors={"rag_quality": 0.38}
        )

        result = build_prompt_node(state)

        assert result.prompt is not None
        assert "customer_data" in result.prompt
        assert "database" in result.prompt
        assert "build_prompt" in result.telemetry_data

    def test_build_prompt_minimal_context(self, sample_commitment):
        """Test building prompt with minimal context."""
        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.asset = AssetURI.from_uri(state.asset_uri)
        state.commitment = sample_commitment
        state.confidence = ConfidenceAssessment(
            score=0.50,
            level="insufficient",
            factors={}
        )

        result = build_prompt_node(state)

        assert result.prompt is not None


class TestLLMCallNode:
    """Tests for llm_call_node."""

    @patch('agent.nodes.llm_call.ChatOpenAI')
    def test_llm_call_success(self, mock_chat, sample_commitment):
        """Test successful LLM call."""
        # Setup mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '{"decision": "in-scope", "reasoning": "Database contains customer PII", "confidence_level": "high", "confidence_score": 0.90}'
        mock_llm.invoke.return_value = mock_response
        mock_chat.return_value = mock_llm

        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.commitment = sample_commitment
        state.prompt = "Test prompt"
        state.confidence = ConfidenceAssessment(score=0.85, level="high", factors={})

        result = llm_call_node(state)

        assert result.response is not None
        assert result.response.decision == "in-scope"
        assert "llm_call" in result.telemetry_data

    @patch('agent.nodes.llm_call.ChatOpenAI')
    def test_llm_call_error(self, mock_chat, sample_commitment):
        """Test LLM call with error."""
        mock_llm = Mock()
        mock_llm.invoke.side_effect = Exception("API Error")
        mock_chat.return_value = mock_llm

        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.commitment = sample_commitment
        state.prompt = "Test prompt"
        state.confidence = ConfidenceAssessment(score=0.85, level="high", factors={})

        result = llm_call_node(state)

        assert len(result.errors) > 0
        assert "llm_call" in result.telemetry_data


class TestSaveDecisionNode:
    """Tests for save_decision_node."""

    @patch('agent.nodes.save_decision.db')
    def test_save_decision_success(self, mock_db, sample_commitment):
        """Test successful decision save."""
        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.asset = AssetURI.from_uri(state.asset_uri)
        state.commitment = sample_commitment
        state.response = ScopingResponse(
            decision="in-scope",
            reasoning="Database contains PII",
            confidence_level="high",
            confidence_score=0.90
        )

        result = save_decision_node(state)

        assert result.decision is not None
        assert mock_db.add_scoping_decision.called
        assert "save_decision" in result.telemetry_data

    @patch('agent.nodes.save_decision.db')
    def test_save_decision_no_response(self, mock_db, sample_commitment):
        """Test save decision when no response exists."""
        state = AgentState(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )
        state.commitment = sample_commitment

        result = save_decision_node(state)

        assert len(result.errors) > 0
        assert not mock_db.add_scoping_decision.called
