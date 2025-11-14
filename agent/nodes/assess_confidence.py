"""Node for assessing confidence in making a decision."""
import time

from config import settings
from storage.schemas import AgentState, ConfidenceAssessment


def assess_confidence_node(state: AgentState) -> AgentState:
    """
    Assess confidence based on available data.

    Factors:
    - RAG chunk relevance and count
    - Similar feedback count and quality
    - Feedback agreement (aligned vs conflicting)
    - Recency of feedback

    Args:
        state: Current agent state

    Returns:
        Updated state with confidence assessment
    """
    start = time.time()

    try:
        factors = {}
        score_components = []

        # Factor 1: RAG context quality (0-0.4)
        if state.rag_context:
            rag_score = 0.0
            if state.rag_context.chunks_retrieved > 0:
                rag_score = min(0.4, state.rag_context.avg_similarity * 0.5)
            factors["rag_avg_similarity"] = state.rag_context.avg_similarity
            factors["rag_chunks_count"] = state.rag_context.chunks_retrieved
            score_components.append(rag_score)
        else:
            factors["rag_avg_similarity"] = 0.0
            factors["rag_chunks_count"] = 0
            score_components.append(0.0)

        # Factor 2: Feedback count and quality (0-0.4)
        feedback_score = 0.0
        if state.feedback_context and state.feedback_context.retrieved_count > 0:
            # Base score from similarity
            feedback_score = state.feedback_context.avg_similarity * 0.2

            # Bonus for multiple feedback entries
            if state.feedback_context.retrieved_count >= 3:
                feedback_score += 0.15
            elif state.feedback_context.retrieved_count >= 2:
                feedback_score += 0.1
            else:
                feedback_score += 0.05

            factors["feedback_count"] = state.feedback_context.retrieved_count
            factors["feedback_avg_similarity"] = state.feedback_context.avg_similarity
            factors["frequency_clusters"] = state.feedback_context.frequency_clusters
        else:
            factors["feedback_count"] = 0
            factors["feedback_avg_similarity"] = 0.0
            factors["frequency_clusters"] = 0

        score_components.append(feedback_score)

        # Factor 3: Feedback agreement (0-0.2)
        agreement_score = 0.0
        if state.similar_feedback:
            # Check if feedback is aligned (all same decision) or conflicting
            decisions = [f.agent_decision for f in state.similar_feedback]
            ratings = [f.rating for f in state.similar_feedback]

            # All same decision = aligned
            if len(set(decisions)) == 1:
                factors["feedback_agreement"] = "aligned"
                agreement_score = 0.2
            elif len(set(decisions)) == 2:
                factors["feedback_agreement"] = "mixed"
                agreement_score = 0.1
            else:
                factors["feedback_agreement"] = "conflicting"
                agreement_score = 0.0

            # Penalty if mostly thumbs down
            thumbs_down_ratio = ratings.count("down") / len(ratings)
            if thumbs_down_ratio > 0.5:
                agreement_score *= 0.5

            factors["thumbs_down_ratio"] = thumbs_down_ratio
        else:
            factors["feedback_agreement"] = "none"
            factors["thumbs_down_ratio"] = 0.0

        score_components.append(agreement_score)

        # Calculate final confidence score
        confidence_score = sum(score_components)

        # Determine confidence level
        if confidence_score >= settings.confidence_high_threshold:
            level = "high"
        elif confidence_score >= settings.confidence_medium_threshold:
            level = "medium"
        elif confidence_score >= settings.confidence_low_threshold:
            level = "low"
        else:
            level = "insufficient"

        # Build reasoning
        reasoning_parts = []
        if state.rag_context and state.rag_context.chunks_retrieved > 0:
            reasoning_parts.append(
                f"Retrieved {state.rag_context.chunks_retrieved} commitment chunks "
                f"(avg similarity: {state.rag_context.avg_similarity:.2f})"
            )
        else:
            reasoning_parts.append("No commitment documentation chunks retrieved")

        if state.feedback_context and state.feedback_context.retrieved_count > 0:
            reasoning_parts.append(
                f"Found {state.feedback_context.retrieved_count} similar past decisions "
                f"(avg similarity: {state.feedback_context.avg_similarity:.2f})"
            )
            if factors.get("feedback_agreement") == "aligned":
                reasoning_parts.append("Past decisions are aligned")
            elif factors.get("feedback_agreement") == "mixed":
                reasoning_parts.append("Past decisions show mixed results")
        else:
            reasoning_parts.append("No similar past decisions found")

        reasoning = ". ".join(reasoning_parts) + "."

        # Create assessment
        state.confidence = ConfidenceAssessment(
            level=level,
            score=confidence_score,
            factors=factors,
            reasoning=reasoning
        )

        # Track telemetry
        state.telemetry_data["confidence_assessment"] = {
            "level": level,
            "score": confidence_score,
            "score_components": {
                "rag": score_components[0],
                "feedback": score_components[1],
                "agreement": score_components[2]
            },
            "factors": factors,
            "reasoning": reasoning,
            "time_ms": (time.time() - start) * 1000
        }

    except Exception as e:
        state.errors.append(f"Confidence assessment error: {str(e)}")
        state.telemetry_data["confidence_assessment"] = {
            "error": str(e),
            "time_ms": (time.time() - start) * 1000
        }

    return state
