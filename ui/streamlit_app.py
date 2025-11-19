"""Streamlit UI for evidencing agent with feedback collection."""
import json
import streamlit as st

from agent.graph import agent
from feedback.collector import feedback_collector
from feedback.processor import feedback_processor
from storage import db, rag_service
from storage.schemas import Commitment


# Page configuration
st.set_page_config(
    page_title="Evidencing Agent",
    page_icon="🔍",
    layout="wide"
)

# Initialize session state
if "decision_result" not in st.session_state:
    st.session_state.decision_result = None
if "show_feedback_form" not in st.session_state:
    st.session_state.show_feedback_form = False


def main():
    """Main Streamlit app."""
    st.title("🔍 Evidencing Agent")
    st.markdown("Asset scoping decisions with human-in-the-loop feedback")

    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Navigation",
        ["Make Decision", "View Decisions", "Manage Commitments", "Statistics", "Checkpoints"]
    )

    if page == "Make Decision":
        make_decision_page()
    elif page == "View Decisions":
        view_decisions_page()
    elif page == "Manage Commitments":
        manage_commitments_page()
    elif page == "Statistics":
        statistics_page()
    elif page == "Checkpoints":
        checkpoints_page()


def make_decision_page():
    """Page for making scoping decisions."""
    st.header("Make Scoping Decision")

    col1, col2 = st.columns(2)

    with col1:
        asset_uri = st.text_input(
            "Asset URI",
            placeholder="asset://database.customer_data.production",
            help="Format: asset://type.descriptor.domain"
        )

    with col2:
        # Get available commitments
        commitments = db.list_commitments()
        if commitments:
            commitment_names = [c.name for c in commitments]
            selected_commitment = st.selectbox("Commitment", commitment_names)
        else:
            st.warning("No commitments found. Please add commitments first.")
            selected_commitment = None

    if st.button("🚀 Analyze", type="primary", disabled=not (asset_uri and selected_commitment)):
        with st.spinner("Processing..."):
            try:
                result = agent.run(
                    asset_uri=asset_uri,
                    commitment_id=selected_commitment
                )
                st.session_state.decision_result = result
                st.session_state.show_feedback_form = True
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return

    # Display results
    if st.session_state.decision_result:
        display_decision_result(st.session_state.decision_result)


def display_decision_result(result):
    """Display decision result with evidence."""
    st.markdown("---")

    # Check for errors
    if result.errors:
        st.error("Errors occurred:")
        for error in result.errors:
            st.write(f"- {error}")
        return

    if not result.response:
        st.error("No response generated")
        return

    response = result.response

    # Display decision
    if response.decision == "insufficient-data":
        st.warning("⚠️ INSUFFICIENT DATA TO DECIDE")

        st.markdown(f"**Reasoning:**\n{response.reasoning}")

        if response.missing_information:
            with st.expander("🔍 Missing Information", expanded=True):
                for item in response.missing_information:
                    st.write(f"- {item}")

        if response.clarifying_questions:
            with st.expander("❓ Clarifying Questions", expanded=True):
                for q in response.clarifying_questions:
                    st.write(f"- {q}")

        if response.partial_analysis:
            with st.expander("📊 Partial Analysis"):
                st.write(response.partial_analysis)

    else:
        # Confident decision
        if response.decision == "in-scope":
            st.success("✅ IN-SCOPE")
        else:
            st.info("❌ OUT-OF-SCOPE")

        st.metric("Confidence", f"{response.confidence_level} ({response.confidence_score:.2f})")

        st.markdown(f"**Reasoning:**\n{response.reasoning}")

        # Evidence
        if response.evidence:
            with st.expander("📊 View Evidence & Reasoning", expanded=False):
                st.markdown(f"**Commitment Analysis:**\n{response.evidence.commitment_analysis}")
                st.markdown(f"**Decision Rationale:**\n{response.evidence.decision_rationale}")

                if response.evidence.asset_characteristics:
                    st.markdown("**Asset Characteristics:**")
                    for char in response.evidence.asset_characteristics:
                        st.write(f"- {char}")

        # Commitment references
        if response.commitment_references:
            with st.expander(f"📚 Commitment References ({len(response.commitment_references)})", expanded=False):
                for idx, ref in enumerate(response.commitment_references):
                    st.markdown(f"**Chunk {idx + 1}** (`{ref.chunk_id}`)")
                    st.text(ref.text[:200] + "..." if len(ref.text) > 200 else ref.text)
                    if ref.relevance:
                        st.info(f"Relevance: {ref.relevance}")
                    st.markdown("---")

        # Similar decisions
        if response.similar_decisions:
            with st.expander(f"🔍 Similar Past Decisions ({len(response.similar_decisions)})", expanded=False):
                for sim in response.similar_decisions:
                    st.markdown(f"**{sim.asset_uri}** → `{sim.decision}` (similarity: {sim.similarity_score:.2f})")
                    st.write(f"📝 {sim.how_it_influenced}")
                    st.markdown("---")

    # Telemetry
    with st.expander("🔧 Telemetry & Debug Info", expanded=False):
        st.json(result.telemetry_data)

    # Feedback form
    if st.session_state.show_feedback_form:
        st.markdown("---")
        st.subheader("💬 Provide Feedback")

        feedback_form(result.decision.id, response.decision)


def feedback_form(decision_id: str, agent_decision: str):
    """Feedback form for a decision."""
    col1, col2 = st.columns([1, 3])

    with col1:
        rating = st.radio(
            "Was this correct?",
            ["👍 Correct", "👎 Incorrect"],
            key=f"rating_{decision_id}"
        )

    with col2:
        human_reason = st.text_area(
            "Explain why this was correct or incorrect:",
            key=f"reason_{decision_id}",
            height=100
        )

        human_correction = None
        if rating == "👎 Incorrect":
            human_correction = st.text_area(
                "What should the correct decision be and why?",
                key=f"correction_{decision_id}",
                height=100,
                placeholder="e.g., 'Should be out-of-scope because the database doesn't contain PII, only anonymized analytics data.'"
            )

    if st.button("Submit Feedback", type="primary"):
        if not human_reason:
            st.error("Please provide a reason for your feedback")
            return

        if rating == "👎 Incorrect" and not human_correction:
            st.error("Please provide the correct decision for thumbs down feedback")
            return

        try:
            rating_value = "up" if rating == "👍 Correct" else "down"
            feedback = feedback_collector.submit_feedback(
                decision_id=decision_id,
                rating=rating_value,
                human_reason=human_reason,
                human_correction=human_correction
            )

            st.success(f"✅ Feedback submitted! (ID: {feedback.id})")
            st.session_state.show_feedback_form = False

        except Exception as e:
            st.error(f"Error submitting feedback: {str(e)}")


def view_decisions_page():
    """Page for viewing past decisions."""
    st.header("Past Decisions")

    # Filters
    col1, col2 = st.columns([3, 1])
    with col1:
        commitments = db.list_commitments()
        commitment_filter = st.selectbox(
            "Filter by Commitment",
            ["All"] + [c.name for c in commitments]
        )
    with col2:
        limit = st.number_input("Show last N", min_value=5, max_value=100, value=20)

    # Get decisions
    decisions = db.list_scoping_decisions(
        commitment_id=commitment_filter if commitment_filter != "All" else None,
        limit=limit
    )

    if not decisions:
        st.info("No decisions found")
        return

    # Display decisions
    for decision in decisions:
        with st.expander(
            f"{'✅' if decision['decision'] == 'in-scope' else '❌' if decision['decision'] == 'out-of-scope' else '⚠️'} "
            f"{decision['asset_uri']} → {decision['decision']} "
            f"(confidence: {decision['confidence_level']})"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Asset:** {decision['asset_uri']}")
                st.write(f"**Commitment:** {decision['commitment_name']}")
            with col2:
                st.write(f"**Decision:** {decision['decision']}")
                st.write(f"**Confidence:** {decision['confidence_level']} ({decision['confidence_score']:.2f})")

            response = json.loads(decision['response'])
            st.markdown(f"**Reasoning:**\n{response['reasoning']}")

            st.write(f"**Decision ID:** `{decision['id']}`")
            st.write(f"**Timestamp:** {decision['timestamp']}")


def manage_commitments_page():
    """Page for managing commitments."""
    st.header("Manage Commitments")

    # Add new commitment
    with st.expander("➕ Add New Commitment", expanded=False):
        name = st.text_input("Commitment Name", placeholder="SOC 2 Type II - CC6.1")
        description = st.text_area("Description (optional)", height=100)
        doc_text = st.text_area(
            "Document Text",
            height=300,
            placeholder="Enter the full document text of the commitment..."
        )
        scoping_criteria = st.text_area(
            "Scoping Criteria (optional)",
            height=150,
            placeholder="How to determine if an asset is in-scope or out-of-scope..."
        )
        domain = st.selectbox(
            "Domain (optional)",
            ["", "security", "privacy", "financial", "operational", "other"]
        )

        if st.button("Add Commitment", type="primary"):
            if not name or not doc_text:
                st.error("Name and Document Text are required")
            else:
                try:
                    commitment = Commitment(
                        name=name,
                        description=description or None,
                        doc_text=doc_text,
                        scoping_criteria=scoping_criteria or None,
                        domain=domain if domain else None
                    )

                    db.add_commitment(commitment)

                    with st.spinner("Processing for RAG..."):
                        chunks = rag_service.process_and_store_commitment(commitment)

                    st.success(f"✅ Commitment added! Created {len(chunks)} chunks for RAG")

                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # List existing commitments
    st.markdown("---")
    st.subheader("Existing Commitments")

    commitments = db.list_commitments()

    if not commitments:
        st.info("No commitments found")
    else:
        for commitment in commitments:
            with st.expander(f"📋 {commitment.name}"):
                if commitment.description:
                    st.write(f"**Description:** {commitment.description}")
                st.write(f"**Domain:** {commitment.domain or 'N/A'}")
                st.write(f"**ID:** `{commitment.id}`")

                st.markdown("**Document Text:**")
                st.text(commitment.doc_text[:500] + "..." if len(commitment.doc_text) > 500 else commitment.doc_text)

                # Show chunk count
                chunks = db.get_commitment_chunks(commitment.id)
                st.write(f"**RAG Chunks:** {len(chunks)}")


def statistics_page():
    """Page for showing statistics."""
    st.header("Statistics & Analytics")

    # Overall stats
    st.subheader("Overall Feedback Statistics")
    stats = feedback_processor.get_feedback_stats()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Feedback", stats["total"])
    col2.metric("👍 Thumbs Up", stats["thumbs_up"])
    col3.metric("👎 Thumbs Down", stats["thumbs_down"])
    col4.metric("Accuracy", f"{stats['accuracy']:.1%}")

    # Per-commitment stats
    st.markdown("---")
    st.subheader("Per-Commitment Statistics")

    commitments = db.list_commitments()
    for commitment in commitments:
        commitment_stats = feedback_processor.get_feedback_stats(commitment.id)
        if commitment_stats["total"] > 0:
            with st.expander(f"{commitment.name} ({commitment_stats['total']} feedback entries)"):
                col1, col2, col3 = st.columns(3)
                col1.metric("👍 Thumbs Up", commitment_stats["thumbs_up"])
                col2.metric("👎 Thumbs Down", commitment_stats["thumbs_down"])
                col3.metric("Accuracy", f"{commitment_stats['accuracy']:.1%}")


def checkpoints_page():
    """Page for viewing decision checkpoints."""
    st.header("💾 Decision Checkpoints")
    st.markdown("View checkpoint history for decision threads (LangGraph 1.0+ feature)")

    # Input thread ID
    thread_id = st.text_input(
        "Thread ID / Session ID",
        placeholder="Enter thread ID from a decision...",
        help="Get this from the decision output or Session ID field"
    )

    if not thread_id:
        st.info("Enter a thread ID to view its checkpoint history")
        return

    # Tabs for different views
    tab1, tab2 = st.tabs(["Checkpoint History", "Current State"])

    with tab1:
        st.subheader("Checkpoint History")

        try:
            checkpoints = agent.get_checkpoint_history(thread_id)

            if not checkpoints:
                st.warning("No checkpoints found for this thread")
                return

            st.success(f"Found {len(checkpoints)} checkpoints")

            # Display each checkpoint
            for idx, checkpoint in enumerate(checkpoints):
                values = checkpoint.get("values", {})
                next_nodes = checkpoint.get("next", [])

                with st.expander(f"Checkpoint {idx + 1}", expanded=(idx == 0)):
                    if next_nodes:
                        st.write(f"**Next nodes:** {', '.join(next_nodes)}")

                    # Show state information
                    if values:
                        col1, col2 = st.columns(2)

                        with col1:
                            if "asset" in values and values["asset"]:
                                asset = values["asset"]
                                st.write(f"**Asset URI:** {asset.get('raw_uri', 'N/A')}")
                                st.write(f"**Type:** {asset.get('asset_type', 'N/A')}")
                                st.write(f"**Domain:** {asset.get('asset_domain', 'N/A')}")

                        with col2:
                            if "commitment_name" in values and values["commitment_name"]:
                                st.write(f"**Commitment:** {values['commitment_name']}")

                            if "confidence" in values and values["confidence"]:
                                conf = values["confidence"]
                                st.write(f"**Confidence:** {conf.get('level', 'N/A')} ({conf.get('score', 0):.2f})")

                            if "response" in values and values["response"]:
                                resp = values["response"]
                                st.write(f"**Decision:** {resp.get('decision', 'N/A')}")

                        # Show telemetry if available
                        if "telemetry_data" in values and values["telemetry_data"]:
                            with st.expander("View Telemetry", expanded=False):
                                st.json(values["telemetry_data"])

        except Exception as e:
            st.error(f"Error loading checkpoints: {str(e)}")

    with tab2:
        st.subheader("Current State")

        try:
            state = agent.get_current_state(thread_id)

            if not state:
                st.warning("No state found for this thread")
                return

            # Display state info
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Asset URI:** {state.asset_uri}")
                if state.asset:
                    st.write(f"**Type:** {state.asset.asset_type}")
                    st.write(f"**Descriptor:** {state.asset.asset_descriptor}")
                    st.write(f"**Domain:** {state.asset.asset_domain}")

            with col2:
                st.write(f"**Commitment:** {state.commitment_name or state.commitment_id}")
                st.write(f"**Session ID:** {state.session_id}")

            st.markdown("---")

            if state.response:
                st.subheader("Decision")

                if state.response.decision == "insufficient-data":
                    st.warning("⚠️ INSUFFICIENT DATA TO DECIDE")
                elif state.response.decision == "in-scope":
                    st.success("✅ IN-SCOPE")
                else:
                    st.info("❌ OUT-OF-SCOPE")

                st.metric("Confidence", f"{state.response.confidence_level} ({state.response.confidence_score:.2f})")
                st.write(f"**Reasoning:** {state.response.reasoning}")

            if state.errors:
                st.error("**Errors:**")
                for error in state.errors:
                    st.write(f"- {error}")

        except Exception as e:
            st.error(f"Error loading current state: {str(e)}")


if __name__ == "__main__":
    main()
