"""Feedback collection for scoping decisions."""
from datetime import datetime
from typing import Literal

from config import settings
from storage import db, embedding_service
from storage.schemas import DecisionFeedback
from storage.vector_store.factory import get_vector_store_from_config
from storage.vector_store.base import VectorDocument


class FeedbackCollector:
    """Collect and store human feedback on decisions."""

    def __init__(self, vector_store=None):
        """
        Initialize feedback collector.

        Args:
            vector_store: Optional vector store instance (defaults to config-based store)
        """
        # Initialize vector store (shared with RAG and feedback processor)
        if vector_store is None:
            self.vector_store = get_vector_store_from_config(settings)
        else:
            self.vector_store = vector_store

    def submit_feedback(
        self,
        decision_id: str,
        rating: Literal["up", "down"],
        human_reason: str,
        human_correction: str | None = None
    ) -> DecisionFeedback:
        """
        Submit feedback for a scoping decision.

        Stores feedback metadata in database and embeddings in vector store.

        Args:
            decision_id: ID of the decision being rated
            rating: "up" for correct, "down" for incorrect
            human_reason: Explanation of why this was correct/incorrect
            human_correction: For thumbs down, what the correct decision should be

        Returns:
            Created feedback entry

        Raises:
            ValueError: If decision not found or thumbs down without correction
        """
        # Get the original decision
        decision_data = db.get_scoping_decision(decision_id)
        if not decision_data:
            raise ValueError(f"Decision not found: {decision_id}")

        # Validate thumbs down has correction
        if rating == "down" and not human_correction:
            raise ValueError("Thumbs down feedback requires a correction")

        # Parse the response JSON
        import json
        response_json = json.loads(decision_data["response"])

        # Get query embedding
        query_embedding = json.loads(decision_data["query_embedding"])

        # Create feedback entry (without embedding for database)
        feedback = DecisionFeedback(
            decision_id=decision_id,
            timestamp=datetime.utcnow(),
            asset_uri=decision_data["asset_uri"],
            commitment_id=decision_data["commitment_id"],
            query_embedding=[],  # Don't store in DB
            agent_decision=decision_data["decision"],
            agent_reasoning=response_json.get("reasoning", ""),
            rating=rating,
            human_reason=human_reason,
            human_correction=human_correction
        )

        # Store metadata in database
        db.add_feedback(feedback)

        # Store vector in vector store
        feedback_text = f"{decision_data['asset_uri']}: {human_reason}"
        if human_correction:
            feedback_text += f" | Correction: {human_correction}"

        vector_doc = VectorDocument(
            id=feedback.id,
            text=feedback_text,
            embedding=query_embedding,
            metadata={
                "type": "feedback",
                "commitment_id": decision_data["commitment_id"],
                "asset_uri": decision_data["asset_uri"],
                "rating": rating,
                "decision": decision_data["decision"]
            }
        )

        self.vector_store.add_documents([vector_doc])

        return feedback

    def get_decision_feedback(self, decision_id: str) -> list[DecisionFeedback]:
        """Get all feedback for a specific decision."""
        return db.list_feedback(decision_id=decision_id)

    def delete_feedback_vector(self, feedback_id: str) -> None:
        """
        Delete feedback vector from vector store.

        Args:
            feedback_id: ID of feedback to delete
        """
        self.vector_store.delete_by_id(feedback_id)


# Global feedback collector instance
feedback_collector = FeedbackCollector()
