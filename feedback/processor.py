"""Feedback processing and analysis."""
from collections import defaultdict

from storage import db, embedding_service
from storage.schemas import DecisionFeedback


class FeedbackProcessor:
    """Process and analyze feedback for patterns."""

    def cluster_similar_feedback(
        self,
        threshold: float = 0.85
    ) -> dict[str, list[DecisionFeedback]]:
        """
        Cluster similar feedback entries.

        Args:
            threshold: Similarity threshold for clustering

        Returns:
            Dictionary mapping cluster_id to list of feedback entries
        """
        all_feedback = db.get_all_feedback()

        if not all_feedback:
            return {}

        # Build similarity matrix
        embeddings = [f.query_embedding for f in all_feedback]
        clusters = defaultdict(list)
        assigned = set()
        cluster_id = 0

        for i, feedback_i in enumerate(all_feedback):
            if i in assigned:
                continue

            # Start new cluster
            current_cluster = f"cluster_{cluster_id}"
            clusters[current_cluster].append(feedback_i)
            assigned.add(i)

            # Find similar feedback
            for j, feedback_j in enumerate(all_feedback[i + 1:], start=i + 1):
                if j in assigned:
                    continue

                similarity = embedding_service.cosine_similarity(
                    embeddings[i],
                    embeddings[j]
                )

                if similarity >= threshold:
                    clusters[current_cluster].append(feedback_j)
                    assigned.add(j)

            cluster_id += 1

        return dict(clusters)

    def get_feedback_stats(self, commitment_id: str | None = None) -> dict:
        """
        Get statistics about feedback.

        Args:
            commitment_id: Optional filter by commitment

        Returns:
            Dictionary with feedback statistics
        """
        feedback = db.list_feedback(commitment_id=commitment_id, limit=1000)

        if not feedback:
            return {
                "total": 0,
                "thumbs_up": 0,
                "thumbs_down": 0,
                "accuracy": 0.0
            }

        thumbs_up = sum(1 for f in feedback if f.rating == "up")
        thumbs_down = sum(1 for f in feedback if f.rating == "down")

        return {
            "total": len(feedback),
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "accuracy": thumbs_up / len(feedback) if feedback else 0.0,
            "by_commitment": commitment_id or "all"
        }


# Global processor instance
feedback_processor = FeedbackProcessor()
