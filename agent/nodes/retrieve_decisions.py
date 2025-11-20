"""Node for retrieving similar prior scoping decisions."""
import json
import time

from config import settings
from storage import db, vector_store
from storage.schemas import AgentState


def retrieve_decisions_node(state: AgentState) -> AgentState:
    """
    Retrieve similar prior scoping decisions using vector search.

    This finds past decisions on similar assets/queries to help maintain
    consistency and learn from prior reasoning.

    Args:
        state: Current agent state with query_embedding

    Returns:
        Updated state with similar_decisions populated
    """
    start = time.time()

    try:
        if not state.query_embedding:
            raise ValueError("Query embedding required for decision retrieval")

        # Search vector store for similar decisions
        results = vector_store.search(
            query_embedding=state.query_embedding,
            top_k=settings.feedback_top_k * 2,  # Get more candidates
            filter_metadata={
                "type": "decision",
                "commitment_id": state.commitment_id
            },
            score_threshold=settings.similarity_threshold
        )

        similar_decisions = []

        for result in results:
            # Get the full decision from database
            decision_id = result.metadata.get("decision_id")
            if not decision_id:
                continue

            decision_data = db.get_scoping_decision(decision_id)
            if not decision_data:
                continue

            # Parse the response JSON
            response_json = json.loads(decision_data["response"])

            # Build decision dict
            similar_decisions.append({
                "decision_id": decision_id,
                "asset_uri": decision_data["asset_uri"],
                "decision": decision_data["decision"],
                "confidence_level": decision_data["confidence_level"],
                "confidence_score": decision_data["confidence_score"],
                "reasoning": response_json.get("reasoning", ""),
                "evidence": response_json.get("evidence"),
                "commitment_references": response_json.get("commitment_references", []),
                "similarity": result.score,
                "created_at": decision_data["created_at"]
            })

        state.similar_decisions = similar_decisions

        # Track telemetry
        state.telemetry_data["decision_retrieval"] = {
            "decisions_found": len(similar_decisions),
            "avg_similarity": (
                sum(d["similarity"] for d in similar_decisions) / len(similar_decisions)
                if similar_decisions else 0.0
            ),
            "top_similarity": similar_decisions[0]["similarity"] if similar_decisions else 0.0,
            "time_ms": (time.time() - start) * 1000
        }

    except Exception as e:
        state.errors.append(f"Decision retrieval error: {str(e)}")
        state.telemetry_data["decision_retrieval"] = {
            "error": str(e),
            "time_ms": (time.time() - start) * 1000
        }

    return state
