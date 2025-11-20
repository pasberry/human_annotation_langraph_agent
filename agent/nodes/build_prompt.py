"""Node for building the LLM prompt with evidence tracking."""
import json
import time

from storage.schemas import AgentState


def build_prompt_node(state: AgentState) -> AgentState:
    """
    Build the prompt for the LLM with RAG context and feedback.

    Args:
        state: Current agent state

    Returns:
        Updated state with prompt built and ready for LLM
    """
    start = time.time()

    try:
        # Build system prompt
        system_prompt = """You are an expert compliance and scoping analyst. Your task is to determine if an asset is IN-SCOPE or OUT-OF-SCOPE for a given commitment (compliance requirement).

You must provide evidence-based decisions with clear reasoning. Always cite the commitment documentation and past decisions that informed your analysis.

Your response must be in JSON format following this exact schema:
{
  "decision": "in-scope" | "out-of-scope" | "insufficient-data",
  "confidence_level": "high" | "medium" | "low" | "insufficient",
  "confidence_score": 0.0-1.0,
  "reasoning": "Your detailed reasoning here",
  "evidence": {
    "commitment_analysis": "How the commitment applies",
    "asset_characteristics": ["list", "of", "relevant", "characteristics"],
    "decision_rationale": "Why this decision was made"
  } | null,
  "commitment_references": [
    {
      "chunk_id": "id",
      "text": "relevant text from commitment",
      "relevance": "why this is relevant",
      "note": "additional context"
    }
  ],
  "similar_decisions": [
    {
      "feedback_id": "id",
      "asset_uri": "uri",
      "decision": "decision",
      "date": "date",
      "similarity_score": 0.0-1.0,
      "how_it_influenced": "explanation"
    }
  ],
  "missing_information": ["what's needed"] | [],
  "clarifying_questions": ["questions"] | [],
  "partial_analysis": "what you could determine" | null
}

IMPORTANT RULES:
1. If decision is "insufficient-data", set evidence to null and populate missing_information and clarifying_questions
2. If decision is "in-scope" or "out-of-scope", populate evidence and set missing_information to empty list
3. Always reference the commitment_references with actual chunk_id values
4. Always explain how similar_decisions influenced your thinking
5. Be precise and cite specific evidence"""

        # Build user prompt
        user_parts = []

        # Asset information
        user_parts.append(f"# Asset to Evaluate")
        user_parts.append(f"Asset URI: {state.asset_uri}")
        if state.asset:
            user_parts.append(f"- Type: {state.asset.asset_type}")
            user_parts.append(f"- Descriptor: {state.asset.asset_descriptor}")
            user_parts.append(f"- Domain: {state.asset.asset_domain}")
        user_parts.append("")

        # Commitment information
        user_parts.append(f"# Commitment")
        if state.commitment:
            user_parts.append(f"Name: {state.commitment.name}")
            if state.commitment.description:
                user_parts.append(f"Description: {state.commitment.description}")
        user_parts.append("")

        # RAG context (commitment documentation)
        if state.rag_chunks:
            user_parts.append(f"# Commitment Documentation (Retrieved via RAG)")
            for idx, chunk in enumerate(state.rag_chunks):
                user_parts.append(f"\n## Chunk {idx + 1} (ID: {chunk.id})")
                user_parts.append(chunk.chunk_text)
                user_parts.append("")
        else:
            user_parts.append("# Commitment Documentation")
            user_parts.append("(No relevant documentation chunks retrieved)")
            user_parts.append("")

        # Similar past decisions (feedback)
        if state.similar_feedback:
            user_parts.append(f"# Similar Past Decisions (Learn from these)")
            for idx, feedback in enumerate(state.similar_feedback):
                user_parts.append(f"\n## Past Decision {idx + 1} (ID: {feedback['feedback_id']})")
                user_parts.append(f"- Asset: {feedback['asset_uri']}")
                user_parts.append(f"- Decision: {feedback['decision']}")
                user_parts.append(f"- Rating: {'👍 Correct' if feedback['rating'] == 'up' else '👎 Incorrect'}")
                user_parts.append(f"- Date: {feedback['created_at'].strftime('%Y-%m-%d')}")
                user_parts.append(f"- Reasoning: {feedback['agent_reasoning']}")
                user_parts.append(f"- Human Feedback: {feedback['human_reason']}")
                if feedback.get('human_correction'):
                    user_parts.append(f"- Correction: {feedback['human_correction']}")
                user_parts.append(f"- Similarity Score: {feedback['similarity']:.3f}")
                if 'frequency_weight' in feedback and feedback['frequency_weight'] > 1.0:
                    user_parts.append(f"- Frequency Weight: {feedback['frequency_weight']:.2f} (appears {feedback.get('cluster_size', 1)} times)")
                user_parts.append("")
        else:
            user_parts.append("# Similar Past Decisions")
            user_parts.append("(No similar past decisions found)")
            user_parts.append("")

        # Confidence assessment
        if state.confidence:
            user_parts.append(f"# Confidence Assessment")
            user_parts.append(f"Based on available data, confidence level: {state.confidence.level}")
            user_parts.append(f"Reasoning: {state.confidence.reasoning}")
            user_parts.append("")

        # Final instruction
        user_parts.append("# Your Task")
        user_parts.append(
            f"Determine if the asset '{state.asset_uri}' is IN-SCOPE or OUT-OF-SCOPE "
            f"for the commitment '{state.commitment_name}'."
        )
        user_parts.append("")
        user_parts.append(
            "Provide your response in the JSON format specified above. "
            "Include evidence, cite commitment chunks by ID, and reference similar decisions."
        )

        if state.confidence and state.confidence.level == "insufficient":
            user_parts.append("")
            user_parts.append(
                "NOTE: Confidence is insufficient. If you cannot make a definitive decision, "
                "respond with decision='insufficient-data' and provide missing_information and clarifying_questions."
            )

        user_prompt = "\n".join(user_parts)

        # Store in telemetry
        state.telemetry_data["prompt_construction"] = {
            "system_prompt_length": len(system_prompt),
            "user_prompt_length": len(user_prompt),
            "rag_chunks_included": len(state.rag_chunks),
            "feedback_examples_included": len(state.similar_feedback),
            "confidence_level": state.confidence.level if state.confidence else None,
            "time_ms": (time.time() - start) * 1000
        }

        # Store prompts in telemetry data for LLM node
        state.telemetry_data["prompts"] = {
            "system": system_prompt,
            "user": user_prompt
        }

    except Exception as e:
        state.errors.append(f"Prompt building error: {str(e)}")
        state.telemetry_data["prompt_construction"] = {
            "error": str(e),
            "time_ms": (time.time() - start) * 1000
        }

    return state
