"""Feedback collection for scoping decisions."""
from datetime import datetime
from typing import Literal

from storage import db, embedding_service
from storage.schemas import DecisionFeedback


class FeedbackCollector:
    """Collect and store human feedback on decisions."""

    def submit_feedback(
        self,
        decision_id: str,
        rating: Literal["up", "down"],
        human_reason: str,
        human_correction: str | None = None
    ) -> DecisionFeedback:
        """
        Submit feedback for a scoping decision.

        Args:
            decision_id: ID of the decision being rated
            rating: "up" for correct, "down" for incorrect
            human_reason: Explanation of why this was correct/incorrect
            human_correction: For thumbs down, what the correct decision should be

        Returns:
            Created feedback entry
        """
        # Get the original decision
        decision_data = db.get_scoping_decision(decision_id)
        if not decision_data:
            raise ValueError(f"Decision not found: {decision_id}")

        # Parse the response JSON
        import json
        response_json = json.loads(decision_data["response"])

        # Create feedback entry
        feedback = DecisionFeedback(
            decision_id=decision_id,
            timestamp=datetime.utcnow(),
            asset_uri=decision_data["asset_uri"],
            commitment_id=decision_data["commitment_id"],
            query_embedding=json.loads(decision_data["query_embedding"]),
            agent_decision=decision_data["decision"],
            agent_reasoning=response_json.get("reasoning", ""),
            rating=rating,
            human_reason=human_reason,
            human_correction=human_correction
        )

        # Store in database
        db.add_feedback(feedback)

        return feedback

    def get_decision_feedback(self, decision_id: str) -> list[DecisionFeedback]:
        """Get all feedback for a specific decision."""
        return db.list_feedback(decision_id=decision_id)


# Global feedback collector instance
feedback_collector = FeedbackCollector()
