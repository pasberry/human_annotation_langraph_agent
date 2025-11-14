"""Tests for database operations."""
import pytest

from storage.schemas import CommitmentChunk, DecisionFeedback, ScopingDecision
from storage.schemas import AssetURI, RAGContext, FeedbackContext, Telemetry
from datetime import datetime


class TestCommitmentOperations:
    """Tests for commitment database operations."""

    def test_add_and_get_commitment(self, temp_db, sample_commitment):
        """Test adding and retrieving a commitment."""
        temp_db.add_commitment(sample_commitment)

        retrieved = temp_db.get_commitment(sample_commitment.id)
        assert retrieved is not None
        assert retrieved.name == sample_commitment.name
        assert retrieved.legal_text == sample_commitment.legal_text

    def test_get_commitment_by_name(self, temp_db, sample_commitment):
        """Test retrieving commitment by name."""
        temp_db.add_commitment(sample_commitment)

        retrieved = temp_db.get_commitment_by_name(sample_commitment.name)
        assert retrieved is not None
        assert retrieved.id == sample_commitment.id

    def test_list_commitments(self, temp_db, sample_commitment):
        """Test listing all commitments."""
        temp_db.add_commitment(sample_commitment)

        commitments = temp_db.list_commitments()
        assert len(commitments) == 1
        assert commitments[0].name == sample_commitment.name

    def test_get_nonexistent_commitment(self, temp_db):
        """Test that getting nonexistent commitment returns None."""
        result = temp_db.get_commitment("nonexistent-id")
        assert result is None


class TestCommitmentChunkOperations:
    """Tests for commitment chunk operations."""

    def test_add_and_get_chunks(self, temp_db, sample_commitment, mock_embedding):
        """Test adding and retrieving commitment chunks."""
        temp_db.add_commitment(sample_commitment)

        chunks = [
            CommitmentChunk(
                commitment_id=sample_commitment.id,
                chunk_text="Test chunk 1",
                chunk_embedding=mock_embedding,
                chunk_index=0
            ),
            CommitmentChunk(
                commitment_id=sample_commitment.id,
                chunk_text="Test chunk 2",
                chunk_embedding=mock_embedding,
                chunk_index=1
            )
        ]

        temp_db.add_commitment_chunks(chunks)

        retrieved = temp_db.get_commitment_chunks(sample_commitment.id)
        assert len(retrieved) == 2
        assert retrieved[0].chunk_text == "Test chunk 1"
        assert retrieved[1].chunk_text == "Test chunk 2"

    def test_get_all_chunks(self, temp_db, sample_commitment, mock_embedding):
        """Test getting all chunks across commitments."""
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

        all_chunks = temp_db.get_all_chunks()
        assert len(all_chunks) >= 1


class TestScopingDecisionOperations:
    """Tests for scoping decision operations."""

    def test_add_scoping_decision(self, temp_db, sample_commitment, sample_asset_uri, mock_embedding):
        """Test adding a scoping decision."""
        temp_db.add_commitment(sample_commitment)

        from storage.schemas import ScopingResponse, Evidence

        decision = ScopingDecision(
            asset_uri=sample_asset_uri,
            asset=AssetURI.from_uri(sample_asset_uri),
            commitment_id=sample_commitment.id,
            commitment_name=sample_commitment.name,
            query_embedding=mock_embedding,
            decision="in-scope",
            confidence_score=0.92,
            confidence_level="high",
            response=ScopingResponse(
                decision="in-scope",
                confidence_level="high",
                confidence_score=0.92,
                reasoning="Test reasoning",
                evidence=Evidence(
                    commitment_analysis="Test analysis",
                    asset_characteristics=["production", "customer_data"],
                    decision_rationale="Test rationale"
                )
            ),
            telemetry=Telemetry(
                session_id="test-session",
                timestamp=datetime.utcnow(),
                query={"test": "data"},
                total_latency_ms=100.0
            ),
            session_id="test-session"
        )

        temp_db.add_scoping_decision(decision)

        retrieved = temp_db.get_scoping_decision(decision.id)
        assert retrieved is not None
        assert retrieved["asset_uri"] == sample_asset_uri
        assert retrieved["decision"] == "in-scope"

    def test_list_scoping_decisions(self, temp_db, sample_commitment, sample_asset_uri, mock_embedding):
        """Test listing scoping decisions."""
        temp_db.add_commitment(sample_commitment)

        from storage.schemas import ScopingResponse, Telemetry

        decision = ScopingDecision(
            asset_uri=sample_asset_uri,
            asset=AssetURI.from_uri(sample_asset_uri),
            commitment_id=sample_commitment.id,
            commitment_name=sample_commitment.name,
            query_embedding=mock_embedding,
            decision="in-scope",
            confidence_score=0.92,
            confidence_level="high",
            response=ScopingResponse(
                decision="in-scope",
                confidence_level="high",
                confidence_score=0.92,
                reasoning="Test reasoning"
            ),
            telemetry=Telemetry(
                session_id="test-session",
                timestamp=datetime.utcnow(),
                query={"test": "data"},
                total_latency_ms=100.0
            ),
            session_id="test-session"
        )

        temp_db.add_scoping_decision(decision)

        decisions = temp_db.list_scoping_decisions(limit=10)
        assert len(decisions) == 1

        # Test filtering by commitment
        filtered = temp_db.list_scoping_decisions(commitment_id=sample_commitment.id, limit=10)
        assert len(filtered) == 1


class TestFeedbackOperations:
    """Tests for feedback operations."""

    def test_add_and_get_feedback(self, temp_db, mock_embedding):
        """Test adding and retrieving feedback."""
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

        temp_db.add_feedback(feedback)

        all_feedback = temp_db.get_all_feedback()
        assert len(all_feedback) == 1
        assert all_feedback[0].rating == "up"

    def test_list_feedback_with_filters(self, temp_db, mock_embedding):
        """Test listing feedback with filters."""
        feedback1 = DecisionFeedback(
            decision_id="test-decision-1",
            asset_uri="asset://database.test.production",
            commitment_id="commitment-1",
            query_embedding=mock_embedding,
            agent_decision="in-scope",
            agent_reasoning="Test",
            rating="up",
            human_reason="Correct"
        )

        feedback2 = DecisionFeedback(
            decision_id="test-decision-2",
            asset_uri="asset://database.test.production",
            commitment_id="commitment-2",
            query_embedding=mock_embedding,
            agent_decision="out-of-scope",
            agent_reasoning="Test",
            rating="down",
            human_reason="Incorrect"
        )

        temp_db.add_feedback(feedback1)
        temp_db.add_feedback(feedback2)

        # Filter by rating
        up_feedback = temp_db.list_feedback(rating="up", limit=10)
        assert len(up_feedback) == 1
        assert up_feedback[0].rating == "up"

        # Filter by commitment
        commitment_feedback = temp_db.list_feedback(commitment_id="commitment-1", limit=10)
        assert len(commitment_feedback) == 1
