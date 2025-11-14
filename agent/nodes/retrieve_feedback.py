"""Node for retrieving relevant past feedback."""
import time
from collections import defaultdict
from datetime import datetime

from config import settings
from storage import db, embedding_service
from storage.schemas import AgentState, DecisionFeedback, FeedbackContext


def retrieve_feedback_node(state: AgentState) -> AgentState:
    """
    Retrieve similar past decisions and feedback.

    Implements frequency weighting and recency boost.

    Args:
        state: Current agent state

    Returns:
        Updated state with similar feedback
    """
    start = time.time()

    try:
        # Get all feedback from database
        all_feedback = db.get_all_feedback()

        if not all_feedback:
            state.feedback_context = FeedbackContext(
                total_feedback_count=0,
                retrieved_count=0,
                avg_similarity=0.0,
                frequency_clusters=0
            )
            state.telemetry_data["feedback_retrieval"] = {
                "total_feedback_count": 0,
                "retrieved_count": 0,
                "time_ms": (time.time() - start) * 1000
            }
            return state

        # Extract embeddings
        feedback_embeddings = [f.query_embedding for f in all_feedback]

        # Find similar feedback
        similar_indices = embedding_service.find_most_similar(
            query_embedding=state.query_embedding,
            candidate_embeddings=feedback_embeddings,
            top_k=settings.feedback_top_k * 2,  # Get more for clustering
            threshold=settings.similarity_threshold
        )

        if not similar_indices:
            state.feedback_context = FeedbackContext(
                total_feedback_count=len(all_feedback),
                retrieved_count=0,
                avg_similarity=0.0,
                frequency_clusters=0
            )
            state.telemetry_data["feedback_retrieval"] = {
                "total_feedback_count": len(all_feedback),
                "retrieved_count": 0,
                "time_ms": (time.time() - start) * 1000
            }
            return state

        # Get feedback entries with similarity scores
        similar_feedback = [
            (all_feedback[idx], score)
            for idx, score in similar_indices
        ]

        # Apply frequency weighting
        # Group similar feedback by commitment and decision type
        clusters = defaultdict(list)
        for feedback, score in similar_feedback:
            key = (feedback.commitment_id, feedback.agent_decision)
            clusters[key].append((feedback, score))

        # Calculate weighted scores
        weighted_feedback = []
        for cluster_key, cluster_items in clusters.items():
            cluster_size = len(cluster_items)
            for feedback, base_score in cluster_items:
                # Frequency boost: more similar feedback = higher weight
                frequency_boost = (cluster_size - 1) * settings.frequency_boost_factor

                # Recency boost: newer feedback gets slight boost
                days_old = (datetime.utcnow() - feedback.created_at).days
                recency_boost = max(0, settings.recency_weight * (1 - days_old / 365))

                final_score = base_score + frequency_boost + recency_boost
                weighted_feedback.append((feedback, base_score, final_score, cluster_size))

        # Sort by final weighted score
        weighted_feedback.sort(key=lambda x: x[2], reverse=True)

        # Take top-k after weighting
        top_feedback = weighted_feedback[:settings.feedback_top_k]

        # Store in state
        state.similar_feedback = [item[0] for item in top_feedback]

        # Calculate context
        avg_similarity = sum(item[1] for item in top_feedback) / len(top_feedback) if top_feedback else 0.0

        state.feedback_context = FeedbackContext(
            total_feedback_count=len(all_feedback),
            retrieved_count=len(top_feedback),
            avg_similarity=avg_similarity,
            frequency_clusters=len(clusters)
        )

        # Track telemetry
        state.telemetry_data["feedback_retrieval"] = {
            "total_feedback_count": len(all_feedback),
            "candidates_after_threshold": len(similar_feedback),
            "retrieved_count": len(top_feedback),
            "avg_base_similarity": avg_similarity,
            "frequency_clusters": len(clusters),
            "top_matches": [
                {
                    "feedback_id": item[0].id,
                    "base_similarity": item[1],
                    "final_score": item[2],
                    "cluster_size": item[3],
                    "rating": item[0].rating,
                    "decision": item[0].agent_decision
                }
                for item in top_feedback
            ],
            "time_ms": (time.time() - start) * 1000
        }

    except Exception as e:
        state.errors.append(f"Feedback retrieval error: {str(e)}")
        state.telemetry_data["feedback_retrieval"] = {
            "error": str(e),
            "time_ms": (time.time() - start) * 1000
        }

    return state
