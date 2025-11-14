"""Node for retrieving relevant past feedback using vector stores."""
import time

from config import settings
from feedback.processor import feedback_processor
from storage import db
from storage.schemas import AgentState, FeedbackContext


def retrieve_feedback_node(state: AgentState) -> AgentState:
    """
    Retrieve similar past decisions and feedback using vector search.

    Uses the feedback processor to search the vector store for similar
    feedback, applying frequency weighting and recency boost.

    Args:
        state: Current agent state

    Returns:
        Updated state with similar feedback
    """
    start = time.time()

    try:
        # Count total feedback
        all_feedback_count = len(db.list_feedback(limit=10000))

        if all_feedback_count == 0:
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

        # Use feedback processor to retrieve similar feedback
        # (it handles vector search, frequency weighting, and sorting)
        similar_feedback_dicts = feedback_processor.retrieve_similar_feedback(
            query_embedding=state.query_embedding,
            commitment_id=state.commitment_id if hasattr(state, 'commitment_id') else None,
            top_k=settings.feedback_top_k,
            threshold=settings.similarity_threshold
        )

        if not similar_feedback_dicts:
            state.feedback_context = FeedbackContext(
                total_feedback_count=all_feedback_count,
                retrieved_count=0,
                avg_similarity=0.0,
                frequency_clusters=0
            )
            state.telemetry_data["feedback_retrieval"] = {
                "total_feedback_count": all_feedback_count,
                "retrieved_count": 0,
                "time_ms": (time.time() - start) * 1000
            }
            return state

        # Calculate average similarity
        avg_similarity = sum(fb["similarity"] for fb in similar_feedback_dicts) / len(similar_feedback_dicts)

        # Count unique clusters (commitment_id, decision pairs)
        unique_clusters = set(
            (fb["commitment_id"], fb["decision"])
            for fb in similar_feedback_dicts
        )

        # Store feedback context
        state.feedback_context = FeedbackContext(
            total_feedback_count=all_feedback_count,
            retrieved_count=len(similar_feedback_dicts),
            avg_similarity=avg_similarity,
            frequency_clusters=len(unique_clusters)
        )

        # Store similar feedback for prompt building
        # Convert dicts back to simplified format for prompts
        state.similar_feedback = similar_feedback_dicts

        # Track telemetry
        state.telemetry_data["feedback_retrieval"] = {
            "total_feedback_count": all_feedback_count,
            "retrieved_count": len(similar_feedback_dicts),
            "avg_similarity": avg_similarity,
            "frequency_clusters": len(unique_clusters),
            "top_matches": [
                {
                    "feedback_id": fb["feedback_id"],
                    "similarity": fb["similarity"],
                    "frequency_weight": fb.get("frequency_weight", 1.0),
                    "cluster_size": fb.get("cluster_size", 1),
                    "rating": fb["rating"],
                    "decision": fb["decision"]
                }
                for fb in similar_feedback_dicts[:5]  # Top 5 for telemetry
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
