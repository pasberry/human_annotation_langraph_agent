"""Tests for Pydantic schemas."""
import pytest
from pydantic import ValidationError

from storage.schemas import (
    AgentState,
    AssetURI,
    Commitment,
    ConfidenceAssessment,
    DecisionFeedback,
    ScopingResponse,
)


class TestAssetURI:
    """Tests for AssetURI model."""

    def test_valid_asset_uri(self):
        """Test parsing a valid asset URI."""
        uri = "asset://database.customer_data.production"
        asset = AssetURI.from_uri(uri)

        assert asset.raw_uri == uri
        assert asset.asset_type == "database"
        assert asset.asset_descriptor == "customer_data"
        assert asset.asset_domain == "production"

    def test_invalid_uri_prefix(self):
        """Test that invalid URI prefix raises error."""
        with pytest.raises(ValueError, match="Invalid asset URI format"):
            AssetURI.from_uri("http://database.customer_data.production")

    def test_invalid_uri_parts(self):
        """Test that invalid number of parts raises error."""
        with pytest.raises(ValueError, match="Expected exactly 3 parts"):
            AssetURI.from_uri("asset://database.customer_data")

    def test_different_asset_types(self):
        """Test different asset types."""
        test_cases = [
            ("asset://api.auth.staging", "api", "auth", "staging"),
            ("asset://cache.session.temporary", "cache", "session", "temporary"),
            ("asset://service.payment.production", "service", "payment", "production"),
        ]

        for uri, expected_type, expected_desc, expected_domain in test_cases:
            asset = AssetURI.from_uri(uri)
            assert asset.asset_type == expected_type
            assert asset.asset_descriptor == expected_desc
            assert asset.asset_domain == expected_domain


class TestCommitment:
    """Tests for Commitment model."""

    def test_create_commitment(self, sample_commitment):
        """Test creating a commitment."""
        assert sample_commitment.name == "Test SOC 2 CC6.1"
        assert sample_commitment.domain == "security"
        assert "SOC 2" in sample_commitment.doc_text
        assert sample_commitment.id is not None

    def test_commitment_validation(self):
        """Test commitment field validation."""
        # Missing required fields should raise error
        with pytest.raises(ValidationError):
            Commitment(name="Test")


class TestScopingResponse:
    """Tests for ScopingResponse model."""

    def test_in_scope_response(self):
        """Test creating an in-scope response."""
        response = ScopingResponse(
            decision="in-scope",
            confidence_level="high",
            confidence_score=0.92,
            reasoning="Database contains customer PII",
            evidence={
                "commitment_analysis": "SOC 2 applies",
                "asset_characteristics": ["production", "customer_data"],
                "decision_rationale": "In scope due to PII"
            }
        )

        assert response.decision == "in-scope"
        assert response.confidence_level == "high"
        assert response.evidence is not None

    def test_insufficient_data_response(self):
        """Test creating an insufficient-data response."""
        response = ScopingResponse(
            decision="insufficient-data",
            confidence_level="insufficient",
            confidence_score=0.3,
            reasoning="Need more information",
            missing_information=["Data types", "Access patterns"],
            clarifying_questions=["What data is stored?"]
        )

        assert response.decision == "insufficient-data"
        assert len(response.missing_information) == 2
        assert len(response.clarifying_questions) == 1

    def test_confidence_score_validation(self):
        """Test that confidence score is validated."""
        # Should accept valid scores
        ScopingResponse(
            decision="in-scope",
            confidence_level="high",
            confidence_score=0.5,
            reasoning="Test"
        )

        # Should reject invalid scores
        with pytest.raises(ValidationError):
            ScopingResponse(
                decision="in-scope",
                confidence_level="high",
                confidence_score=1.5,  # > 1.0
                reasoning="Test"
            )


class TestConfidenceAssessment:
    """Tests for ConfidenceAssessment model."""

    def test_confidence_levels(self):
        """Test different confidence levels."""
        levels = ["high", "medium", "low", "insufficient"]

        for level in levels:
            assessment = ConfidenceAssessment(
                level=level,
                score=0.5,
                factors={"test": "value"},
                reasoning="Test reasoning"
            )
            assert assessment.level == level

    def test_invalid_confidence_level(self):
        """Test that invalid confidence level raises error."""
        with pytest.raises(ValidationError):
            ConfidenceAssessment(
                level="invalid",
                score=0.5,
                factors={},
                reasoning="Test"
            )


class TestAgentState:
    """Tests for AgentState model."""

    def test_create_agent_state(self, sample_asset_uri):
        """Test creating agent state."""
        state = AgentState(
            asset_uri=sample_asset_uri,
            commitment_id="test-commitment",
        )

        assert state.asset_uri == sample_asset_uri
        assert state.commitment_id == "test-commitment"
        assert state.session_id is not None  # Auto-generated
        assert state.errors == []

    def test_agent_state_with_asset(self, sample_asset_uri):
        """Test agent state with parsed asset."""
        asset = AssetURI.from_uri(sample_asset_uri)
        state = AgentState(
            asset_uri=sample_asset_uri,
            commitment_id="test-commitment",
            asset=asset
        )

        assert state.asset.asset_type == "database"


class TestDecisionFeedback:
    """Tests for DecisionFeedback model."""

    def test_create_feedback(self, mock_embedding):
        """Test creating decision feedback."""
        feedback = DecisionFeedback(
            decision_id="test-decision",
            asset_uri="asset://database.test.production",
            commitment_id="test-commitment",
            query_embedding=mock_embedding,
            agent_decision="in-scope",
            agent_reasoning="Test reasoning",
            rating="up",
            human_reason="Correct decision"
        )

        assert feedback.rating == "up"
        assert feedback.id is not None
        assert feedback.frequency_weight == 1.0

    def test_feedback_with_correction(self, mock_embedding):
        """Test feedback with correction."""
        feedback = DecisionFeedback(
            decision_id="test-decision",
            asset_uri="asset://database.test.production",
            commitment_id="test-commitment",
            query_embedding=mock_embedding,
            agent_decision="in-scope",
            agent_reasoning="Test reasoning",
            rating="down",
            human_reason="Incorrect",
            human_correction="Should be out-of-scope because..."
        )

        assert feedback.rating == "down"
        assert feedback.human_correction is not None
