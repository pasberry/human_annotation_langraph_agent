"""LangGraph workflow definition for evidencing agent.

LangGraph 1.0+ and LangChain 1.0+ compatible implementation with checkpointing.
"""
import time
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agent.nodes.assess_confidence import assess_confidence_node
from agent.nodes.build_prompt import build_prompt_node
from agent.nodes.llm_call import llm_call_node
from agent.nodes.parse_asset import parse_asset_node
from agent.nodes.retrieve_feedback import retrieve_feedback_node
from agent.nodes.retrieve_rag import retrieve_rag_node
from agent.nodes.save_decision import save_decision_node
from storage.schemas import AgentState


# Define the workflow
def create_evidencing_graph():
    """
    Create the LangGraph workflow for evidencing decisions.

    LangGraph 1.0+ features used:
    - Pydantic models for type-safe state management (best practice)
    - Automatic state merging and validation
    - Support for checkpointing and persistence (via langgraph-checkpoint)
    - Improved error handling and debugging

    Workflow:
    1. Parse asset URI
    2. Retrieve commitment documentation (RAG)
    3. Retrieve similar past feedback
    4. Assess confidence
    5. Build prompt with evidence
    6. Call LLM for decision (LangChain 1.0+)
    7. Save decision to database

    Returns:
        Compiled LangGraph workflow
    """
    # Create workflow with Pydantic state model (LangGraph 1.0+ best practice)
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("parse_asset", parse_asset_node)
    workflow.add_node("retrieve_rag", retrieve_rag_node)
    workflow.add_node("retrieve_feedback", retrieve_feedback_node)
    workflow.add_node("assess_confidence", assess_confidence_node)
    workflow.add_node("build_prompt", build_prompt_node)
    workflow.add_node("llm_call", llm_call_node)
    workflow.add_node("save_decision", save_decision_node)

    # Define edges (workflow flow)
    workflow.set_entry_point("parse_asset")

    workflow.add_edge("parse_asset", "retrieve_rag")
    workflow.add_edge("retrieve_rag", "retrieve_feedback")
    workflow.add_edge("retrieve_feedback", "assess_confidence")
    workflow.add_edge("assess_confidence", "build_prompt")
    workflow.add_edge("build_prompt", "llm_call")
    workflow.add_edge("llm_call", "save_decision")
    workflow.add_edge("save_decision", END)

    # Compile graph with checkpointing (LangGraph 1.0+ feature)
    # MemorySaver stores checkpoints in memory (for production, use SqliteSaver or PostgresSaver)
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


class EvidencingAgent:
    """Evidencing agent for scoping decisions with checkpointing support."""

    def __init__(self):
        """Initialize the agent with compiled graph."""
        self.graph = create_evidencing_graph()

    def run(
        self,
        asset_uri: str,
        commitment_id: str,
        session_id: str | None = None,
        thread_id: str | None = None
    ) -> AgentState:
        """
        Run the evidencing agent to make a scoping decision.

        Args:
            asset_uri: Asset URI in format asset://type.descriptor.domain
            commitment_id: Commitment ID or name
            session_id: Optional session ID for tracking
            thread_id: Optional thread ID for checkpointing (defaults to session_id)

        Returns:
            Final agent state with decision
        """
        # Create initial state
        initial_state = AgentState(
            asset_uri=asset_uri,
            commitment_id=commitment_id,
            session_id=session_id or "",
            start_time=time.time()
        )

        # Use thread_id for checkpoint tracking (defaults to session_id)
        config = {"configurable": {"thread_id": thread_id or session_id or initial_state.session_id}}

        # Run the graph with checkpointing
        final_state = self.graph.invoke(initial_state, config=config)

        return final_state

    def get_checkpoint_history(self, thread_id: str) -> list[dict]:
        """
        Get checkpoint history for a thread.

        Args:
            thread_id: Thread ID to get history for

        Returns:
            List of checkpoint states
        """
        config = {"configurable": {"thread_id": thread_id}}
        checkpoints = []

        try:
            # Get checkpoint history from the graph
            for state in self.graph.get_state_history(config):
                checkpoints.append({
                    "checkpoint_id": state.config.get("configurable", {}).get("checkpoint_id"),
                    "values": state.values,
                    "next": state.next,
                    "metadata": state.metadata,
                    "created_at": state.created_at if hasattr(state, "created_at") else None
                })
        except Exception as e:
            print(f"Error getting checkpoint history: {e}")

        return checkpoints

    def get_current_state(self, thread_id: str) -> Optional[AgentState]:
        """
        Get the current state for a thread.

        Args:
            thread_id: Thread ID to get state for

        Returns:
            Current state or None if not found
        """
        config = {"configurable": {"thread_id": thread_id}}

        try:
            state = self.graph.get_state(config)
            if state and state.values:
                return AgentState(**state.values)
        except Exception as e:
            print(f"Error getting current state: {e}")

        return None


# Create global agent instance
agent = EvidencingAgent()
