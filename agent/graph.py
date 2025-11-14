"""LangGraph workflow definition for evidencing agent."""
import time
from typing import TypedDict

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

    Workflow:
    1. Parse asset URI
    2. Retrieve commitment documentation (RAG)
    3. Retrieve similar past feedback
    4. Assess confidence
    5. Build prompt with evidence
    6. Call LLM for decision
    7. Save decision to database

    Returns:
        Compiled LangGraph workflow
    """
    # Create workflow
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

    # Compile graph
    return workflow.compile()


class EvidencingAgent:
    """Evidencing agent for scoping decisions."""

    def __init__(self):
        """Initialize the agent with compiled graph."""
        self.graph = create_evidencing_graph()

    def run(
        self,
        asset_uri: str,
        commitment_id: str,
        session_id: str | None = None
    ) -> AgentState:
        """
        Run the evidencing agent to make a scoping decision.

        Args:
            asset_uri: Asset URI in format asset://type.descriptor.domain
            commitment_id: Commitment ID or name
            session_id: Optional session ID for tracking

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

        # Run the graph
        final_state = self.graph.invoke(initial_state)

        return final_state


# Create global agent instance
agent = EvidencingAgent()
