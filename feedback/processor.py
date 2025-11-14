"""Feedback processing and analysis using vector stores."""
from collections import defaultdict
from typing import List, Optional

from config import settings
from storage import db, embedding_service
from storage.schemas import DecisionFeedback
from storage.vector_store.factory import get_vector_store_from_config
from storage.vector_store.base import VectorDocument, SimilarityResult


class FeedbackProcessor:
    """Process and analyze feedback for patterns using vector stores."""

    def __init__(self, vector_store=None):
        """
        Initialize feedback processor.

        Args:
            vector_store: Optional vector store instance (defaults to config-based store)
        """
        # Initialize vector store (shared with RAG service)
        if vector_store is None:
            self.vector_store = get_vector_store_from_config(settings)
        else:
            self.vector_store = vector_store

    def retrieve_similar_feedback(
        self,
        query_embedding: List[float],
        commitment_id: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.70
    ) -> List[dict]:
        """
        Retrieve similar past feedback using vector search.

        Args:
            query_embedding: Query embedding vector
            commitment_id: Optional commitment ID to filter by
            top_k: Number of results to return
            threshold: Minimum similarity threshold

        Returns:
            List of feedback entries with similarity scores and frequency weights
        """
        # Build metadata filter
        filter_metadata = {"type": "feedback"}
        if commitment_id:
            filter_metadata["commitment_id"] = commitment_id

        # Search vector store
        results: List[SimilarityResult] = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Get more for frequency clustering
            filter_metadata=filter_metadata,
            score_threshold=threshold
        )

        if not results:
            return []

        # Fetch full feedback metadata from database
        feedback_ids = [r.id for r in results]
        all_feedback = db.list_feedback(limit=1000)  # Get all feedback
        feedback_dict = {fb.id: fb for fb in all_feedback if fb.id in feedback_ids}

        # Build results with similarity scores
        similar_feedback = []
        for result in results:
            if result.id in feedback_dict:
                fb = feedback_dict[result.id]
                similar_feedback.append({
                    "feedback_id": fb.id,
                    "asset_uri": fb.asset_uri,
                    "decision": fb.agent_decision,
                    "rating": fb.rating,
                    "human_reason": fb.human_reason,
                    "human_correction": fb.human_correction,
                    "similarity": result.score,
                    "created_at": fb.created_at,
                    "commitment_id": fb.commitment_id
                })

        # Apply frequency weighting
        # Group similar feedback by commitment and decision type
        clusters = defaultdict(list)
        for fb in similar_feedback:
            key = (fb["commitment_id"], fb["decision"])
            clusters[key].append(fb)

        # Calculate frequency weights
        for cluster_items in clusters.values():
            cluster_size = len(cluster_items)
            for fb in cluster_items:
                # Frequency boost: more similar feedback = higher weight
                frequency_boost = (cluster_size - 1) * settings.frequency_boost_factor
                fb["frequency_weight"] = 1.0 + frequency_boost
                fb["cluster_size"] = cluster_size

        # Sort by similarity * frequency_weight
        similar_feedback.sort(
            key=lambda x: x["similarity"] * x.get("frequency_weight", 1.0),
            reverse=True
        )

        # Return top-k after weighting
        return similar_feedback[:top_k]

    def cluster_similar_feedback(
        self,
        commitment_id: Optional[str] = None,
        threshold: float = 0.85
    ) -> List[List[dict]]:
        """
        Cluster similar feedback entries.

        Args:
            commitment_id: Optional commitment ID to filter by
            threshold: Similarity threshold for clustering

        Returns:
            List of clusters (each cluster is a list of feedback entries)
        """
        # Get all feedback
        all_feedback = db.list_feedback(commitment_id=commitment_id, limit=1000)

        if not all_feedback:
            return []

        # Build clusters using embeddings
        embeddings = [f.query_embedding for f in all_feedback]
        clusters = []
        assigned = set()

        for i, feedback_i in enumerate(all_feedback):
            if i in assigned:
                continue

            # Start new cluster
            current_cluster = [feedback_i]
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
                    current_cluster.append(feedback_j)
                    assigned.add(j)

            clusters.append(current_cluster)

        return clusters

    def get_feedback_stats(self, commitment_id: Optional[str] = None) -> dict:
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
