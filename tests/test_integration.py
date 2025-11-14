"""Integration tests for the complete workflow."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from agent.graph import EvidencingAgent, create_evidencing_graph
from storage.schemas import AgentState, Commitment


class TestEvidencingAgent:
    """Integration tests for the evidencing agent."""

    @patch('agent.nodes.llm_call.ChatOpenAI')
    @patch('agent.nodes.save_decision.db')
    @patch('agent.nodes.retrieve_feedback.feedback_processor')
    @patch('agent.nodes.retrieve_rag.rag_service')
    @patch('agent.nodes.retrieve_rag.embedding_service')
    @patch('agent.nodes.retrieve_rag.db')
    def test_complete_workflow_in_scope(
        self,
        mock_db,
        mock_embed,
        mock_rag,
        mock_feedback,
        mock_save_db,
        mock_chat,
        sample_commitment,
        mock_embedding
    ):
        """Test complete workflow resulting in in-scope decision."""
        # Setup mocks
        mock_db.get_commitment_by_name.return_value = sample_commitment
        mock_embed.embed_text.return_value = mock_embedding
        mock_rag.get_commitment_context.return_value = {
            "chunks": ["Production databases require controls"],
            "scores": [0.95],
            "avg_similarity": 0.95,
            "top_similarity": 0.95,
            "num_chunks": 1
        }
        mock_feedback.retrieve_similar_feedback.return_value = []

        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "decision": "in-scope",
            "reasoning": "This database is in production and contains customer data, requiring access controls per SOC 2 CC6.1",
            "confidence_level": "high",
            "confidence_score": 0.90,
            "evidence": {
                "commitment_analysis": "SOC 2 CC6.1 requires logical access controls for systems that store sensitive data",
                "decision_rationale": "Production customer database falls under this requirement",
                "asset_characteristics": ["production environment", "customer data storage"]
            },
            "commitment_references": [],
            "similar_decisions": []
        }
        '''
        mock_llm.invoke.return_value = mock_response
        mock_chat.return_value = mock_llm

        # Run agent
        agent = EvidencingAgent()
        result = agent.run(
            asset_uri="asset://database.customer_data.production",
            commitment_id="test-commitment"
        )

        # Verify result
        assert result is not None
        assert result.response is not None
        assert result.response.decision == "in-scope"
        assert result.response.confidence_level == "high"
        assert result.decision is not None
        assert len(result.errors) == 0

    @patch('agent.nodes.llm_call.ChatOpenAI')
    @patch('agent.nodes.save_decision.db')
    @patch('agent.nodes.retrieve_feedback.feedback_processor')
    @patch('agent.nodes.retrieve_rag.rag_service')
    @patch('agent.nodes.retrieve_rag.embedding_service')
    @patch('agent.nodes.retrieve_rag.db')
    def test_complete_workflow_out_of_scope(
        self,
        mock_db,
        mock_embed,
        mock_rag,
        mock_feedback,
        mock_save_db,
        mock_chat,
        sample_commitment,
        mock_embedding
    ):
        """Test complete workflow resulting in out-of-scope decision."""
        # Setup mocks
        mock_db.get_commitment_by_name.return_value = sample_commitment
        mock_embed.embed_text.return_value = mock_embedding
        mock_rag.get_commitment_context.return_value = {
            "chunks": ["Test environments are excluded from scope"],
            "scores": [0.90],
            "avg_similarity": 0.90,
            "top_similarity": 0.90,
            "num_chunks": 1
        }
        mock_feedback.retrieve_similar_feedback.return_value = []

        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "decision": "out-of-scope",
            "reasoning": "This is a development database, which is explicitly excluded from SOC 2 scope",
            "confidence_level": "high",
            "confidence_score": 0.88,
            "evidence": {
                "commitment_analysis": "SOC 2 CC6.1 applies to production systems only",
                "decision_rationale": "Development environments are out of scope",
                "asset_characteristics": ["development environment", "non-production"]
            }
        }
        '''
        mock_llm.invoke.return_value = mock_response
        mock_chat.return_value = mock_llm

        # Run agent
        agent = EvidencingAgent()
        result = agent.run(
            asset_uri="asset://database.test_data.development",
            commitment_id="test-commitment"
        )

        # Verify result
        assert result.response.decision == "out-of-scope"
        assert result.response.confidence_level == "high"

    @patch('agent.nodes.llm_call.ChatOpenAI')
    @patch('agent.nodes.save_decision.db')
    @patch('agent.nodes.retrieve_feedback.feedback_processor')
    @patch('agent.nodes.retrieve_rag.rag_service')
    @patch('agent.nodes.retrieve_rag.embedding_service')
    @patch('agent.nodes.retrieve_rag.db')
    def test_complete_workflow_insufficient_data(
        self,
        mock_db,
        mock_embed,
        mock_rag,
        mock_feedback,
        mock_save_db,
        mock_chat,
        sample_commitment,
        mock_embedding
    ):
        """Test complete workflow with insufficient data."""
        # Setup mocks with low quality RAG
        mock_db.get_commitment_by_name.return_value = sample_commitment
        mock_embed.embed_text.return_value = mock_embedding
        mock_rag.get_commitment_context.return_value = {
            "chunks": ["Some vague text"],
            "scores": [0.50],
            "avg_similarity": 0.50,
            "top_similarity": 0.50,
            "num_chunks": 1
        }
        mock_feedback.retrieve_similar_feedback.return_value = []

        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "decision": "insufficient-data",
            "reasoning": "Cannot determine scope without more information about the API's data handling",
            "confidence_level": "insufficient",
            "confidence_score": 0.45,
            "missing_information": ["API data types", "Authentication methods"],
            "clarifying_questions": ["What type of data does this API handle?", "Is this API customer-facing?"]
        }
        '''
        mock_llm.invoke.return_value = mock_response
        mock_chat.return_value = mock_llm

        # Run agent
        agent = EvidencingAgent()
        result = agent.run(
            asset_uri="asset://api.unknown_service.production",
            commitment_id="test-commitment"
        )

        # Verify result
        assert result.response.decision == "insufficient-data"
        assert result.response.confidence_level == "insufficient"
        assert len(result.response.missing_information) > 0

    @patch('agent.nodes.retrieve_rag.db')
    def test_workflow_with_missing_commitment(self, mock_db):
        """Test workflow when commitment is not found."""
        mock_db.get_commitment_by_name.return_value = None

        agent = EvidencingAgent()
        result = agent.run(
            asset_uri="asset://database.test.production",
            commitment_id="nonexistent-commitment"
        )

        # Should have error about missing commitment
        assert len(result.errors) > 0
        assert any("Commitment not found" in error for error in result.errors)

    def test_workflow_with_invalid_asset_uri(self):
        """Test workflow with invalid asset URI."""
        agent = EvidencingAgent()
        result = agent.run(
            asset_uri="invalid-uri-format",
            commitment_id="test-commitment"
        )

        # Should have error about parsing
        assert len(result.errors) > 0
        assert any("parsing" in error.lower() for error in result.errors)


class TestCheckpointing:
    """Tests for checkpointing functionality."""

    @patch('agent.nodes.llm_call.ChatOpenAI')
    @patch('agent.nodes.save_decision.db')
    @patch('agent.nodes.retrieve_feedback.feedback_processor')
    @patch('agent.nodes.retrieve_rag.rag_service')
    @patch('agent.nodes.retrieve_rag.embedding_service')
    @patch('agent.nodes.retrieve_rag.db')
    def test_checkpoint_creation(
        self,
        mock_db,
        mock_embed,
        mock_rag,
        mock_feedback,
        mock_save_db,
        mock_chat,
        sample_commitment,
        mock_embedding
    ):
        """Test that checkpoints are created during workflow."""
        # Setup mocks
        mock_db.get_commitment_by_name.return_value = sample_commitment
        mock_embed.embed_text.return_value = mock_embedding
        mock_rag.get_commitment_context.return_value = {
            "chunks": ["Test"],
            "scores": [0.90],
            "avg_similarity": 0.90,
            "top_similarity": 0.90,
            "num_chunks": 1
        }
        mock_feedback.retrieve_similar_feedback.return_value = []

        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "decision": "in-scope",
            "reasoning": "Test",
            "confidence_level": "high",
            "confidence_score": 0.90
        }
        '''
        mock_llm.invoke.return_value = mock_response
        mock_chat.return_value = mock_llm

        # Run agent with specific thread_id
        agent = EvidencingAgent()
        thread_id = "test-thread-123"
        result = agent.run(
            asset_uri="asset://database.test.production",
            commitment_id="test-commitment",
            thread_id=thread_id
        )

        # Get checkpoint history
        checkpoints = agent.get_checkpoint_history(thread_id)

        # Should have checkpoints from workflow execution
        assert len(checkpoints) > 0

    @patch('agent.nodes.llm_call.ChatOpenAI')
    @patch('agent.nodes.save_decision.db')
    @patch('agent.nodes.retrieve_feedback.feedback_processor')
    @patch('agent.nodes.retrieve_rag.rag_service')
    @patch('agent.nodes.retrieve_rag.embedding_service')
    @patch('agent.nodes.retrieve_rag.db')
    def test_get_current_state(
        self,
        mock_db,
        mock_embed,
        mock_rag,
        mock_feedback,
        mock_save_db,
        mock_chat,
        sample_commitment,
        mock_embedding
    ):
        """Test getting current state for a thread."""
        # Setup mocks
        mock_db.get_commitment_by_name.return_value = sample_commitment
        mock_embed.embed_text.return_value = mock_embedding
        mock_rag.get_commitment_context.return_value = {
            "chunks": ["Test"],
            "scores": [0.90],
            "avg_similarity": 0.90,
            "top_similarity": 0.90,
            "num_chunks": 1
        }
        mock_feedback.retrieve_similar_feedback.return_value = []

        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "decision": "in-scope",
            "reasoning": "Test",
            "confidence_level": "high",
            "confidence_score": 0.90
        }
        '''
        mock_llm.invoke.return_value = mock_response
        mock_chat.return_value = mock_llm

        # Run agent
        agent = EvidencingAgent()
        thread_id = "test-thread-456"
        result = agent.run(
            asset_uri="asset://database.test.production",
            commitment_id="test-commitment",
            thread_id=thread_id
        )

        # Get current state
        state = agent.get_current_state(thread_id)

        # Should return final state
        assert state is not None
        assert state.asset_uri == "asset://database.test.production"
        assert state.response is not None


class TestGraphStructure:
    """Tests for graph structure."""

    def test_graph_creation(self):
        """Test that graph is created with correct structure."""
        graph = create_evidencing_graph()

        # Graph should be compiled
        assert graph is not None

        # Should have checkpointer
        assert hasattr(graph, 'checkpointer')

    def test_agent_initialization(self):
        """Test agent initialization."""
        agent = EvidencingAgent()

        assert agent.graph is not None
        assert hasattr(agent, 'run')
        assert hasattr(agent, 'get_checkpoint_history')
        assert hasattr(agent, 'get_current_state')
