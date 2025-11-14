"""Node for saving the scoping decision to database."""
import time
from datetime import datetime

from storage import db
from storage.schemas import AgentState, ScopingDecision, Telemetry


def save_decision_node(state: AgentState) -> AgentState:
    """
    Save the scoping decision to the database.

    Args:
        state: Current agent state with response

    Returns:
        Updated state with decision saved
    """
    start = time.time()

    try:
        if not state.response:
            raise ValueError("No response to save. LLM call must complete first.")

        # Calculate total latency
        total_latency_ms = (time.time() - state.start_time) * 1000 if state.start_time else 0

        # Build telemetry
        telemetry = Telemetry(
            session_id=state.session_id,
            timestamp=datetime.utcnow(),
            query={
                "asset_uri": state.asset_uri,
                "commitment_id": state.commitment_id,
                "commitment_name": state.commitment_name,
                "query_embedding_dim": len(state.query_embedding)
            },
            rag_retrieval=state.telemetry_data.get("rag_retrieval"),
            feedback_retrieval=state.telemetry_data.get("feedback_retrieval"),
            confidence_assessment=state.telemetry_data.get("confidence_assessment"),
            prompt_construction=state.telemetry_data.get("prompt_construction"),
            llm_call=state.telemetry_data.get("llm_call"),
            total_latency_ms=total_latency_ms,
            errors=state.errors
        )

        # Create decision record
        decision = ScopingDecision(
            timestamp=datetime.utcnow(),
            asset_uri=state.asset_uri,
            asset=state.asset,
            commitment_id=state.commitment_id,
            commitment_name=state.commitment_name or state.commitment_id,
            query_embedding=state.query_embedding,
            decision=state.response.decision,
            confidence_score=state.response.confidence_score,
            confidence_level=state.response.confidence_level,
            response=state.response,
            rag_context=state.rag_context,
            feedback_context=state.feedback_context,
            telemetry=telemetry,
            session_id=state.session_id
        )

        # Save to database
        db.add_scoping_decision(decision)

        state.decision = decision

        # Track telemetry
        state.telemetry_data["save_decision"] = {
            "decision_id": decision.id,
            "total_latency_ms": total_latency_ms,
            "time_ms": (time.time() - start) * 1000
        }

    except Exception as e:
        state.errors.append(f"Save decision error: {str(e)}")
        state.telemetry_data["save_decision"] = {
            "error": str(e),
            "time_ms": (time.time() - start) * 1000
        }

    return state
