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
        system_prompt = """# WHO ARE YOU?

You are an expert in purpose limitation and data governance. Your role is to determine whether a specific asset is IN-SCOPE or OUT-OF-SCOPE for a given commitment.

## Your Responsibilities

1. **Analyze Commitment Language**: Carefully read the commitment document to understand what data is protected and for what purpose.

2. **Use Research Tools**: You have access to tools that provide metadata, lineage, and context about assets. Use these tools to gather evidence before making decisions.

3. **Learn from Prior Decisions**: Review similar past decisions to maintain consistency and learn from established patterns.

4. **Weight Human Feedback Most Heavily**: When human experts have corrected or validated decisions on similar assets, their feedback takes precedence. This is the most valuable signal.

5. **Cite All Sources**: Every decision must reference:
   - Specific sections of the commitment document (by chunk ID)
   - Similar prior decisions that influenced your thinking
   - Human feedback that guided your reasoning
   - Research findings from tools

6. **Admit Uncertainty**: If you lack sufficient information to make a confident decision, you MUST respond with "insufficient-data". Never guess. A human expert will be flagged to provide guidance.

## Performance Standards

- **Trustworthiness**: Every decision must be evidence-based and fully traceable
- **Consistency**: Similar assets should receive similar decisions unless human feedback indicates otherwise
- **Precision**: Use exact quotes and specific references
- **Humility**: State when you need more information rather than making unsupported decisions

---

## OUTPUT FORMAT

Your response must be in JSON format following this exact schema:

{
  "decision": "in-scope" | "out-of-scope" | "insufficient-data",
  "confidence_level": "high" | "medium" | "low" | "insufficient",
  "confidence_score": 0.0-1.0,
  "reasoning": "Your detailed reasoning here",
  "evidence": {
    "commitment_analysis": "How the commitment applies to this asset",
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
      "how_it_influenced": "detailed explanation of how this past decision influenced your thinking"
    }
  ],
  "missing_information": ["what's needed"] | [],
  "clarifying_questions": ["questions for human expert"] | [],
  "partial_analysis": "what you could determine despite missing data" | null
}

---

## CRITICAL RULES

1. **If decision is "insufficient-data"**: Set evidence to null and populate missing_information and clarifying_questions. Do not guess.

2. **If decision is "in-scope" or "out-of-scope"**: You MUST populate evidence with detailed analysis. Empty evidence is unacceptable.

3. **Always reference commitment_references**: Use actual chunk_id values from the commitment documentation provided below.

4. **Always explain similar_decisions influence**: For each similar decision, explain in detail how it influenced your current decision. Vague statements like "provided context" are insufficient.

5. **Human feedback is authoritative**: If human feedback contradicts your initial analysis, the human feedback should guide your decision unless you have strong evidence otherwise.

6. **Cite specific evidence**: Use exact quotes, specific field names, concrete examples. Avoid generalizations.

7. **No assumptions**: If the asset's purpose, data fields, or domain are unclear, mark as "insufficient-data" and request specific information.

---
"""

        # Build user prompt
        user_parts = []

        # Header
        user_parts.append("# ASSET SCOPING DECISION REQUEST")
        user_parts.append("")
        user_parts.append(f"**Asset URI**: `{state.asset_uri}`")
        if state.asset:
            user_parts.append(f"**Asset Type**: {state.asset.asset_type}")
            user_parts.append(f"**Asset Descriptor**: {state.asset.asset_descriptor}")
            user_parts.append(f"**Asset Domain**: {state.asset.asset_domain}")
        user_parts.append("")
        user_parts.append(f"**Commitment**: {state.commitment_name}")
        user_parts.append("")
        user_parts.append("---")
        user_parts.append("")

        # Section 1: The Commitment Language
        user_parts.append("## THE COMMITMENT LANGUAGE")
        user_parts.append("")
        if state.commitment and state.commitment.description:
            user_parts.append(f"**Purpose**: {state.commitment.description}")
            user_parts.append("")

        if state.rag_chunks:
            user_parts.append("**Relevant Sections** (retrieved via semantic search):")
            user_parts.append("")
            for idx, chunk in enumerate(state.rag_chunks):
                user_parts.append(f"### Chunk {idx + 1}")
                user_parts.append(f"**ID**: `{chunk.id}`")
                user_parts.append(f"**Content**:")
                user_parts.append(f"```")
                user_parts.append(chunk.chunk_text)
                user_parts.append(f"```")
                user_parts.append("")
        else:
            user_parts.append("*No relevant commitment documentation chunks were retrieved.*")
            user_parts.append("")
            user_parts.append("⚠️ **WARNING**: Without commitment documentation, you likely have insufficient data to make a decision.")
            user_parts.append("")

        user_parts.append("---")
        user_parts.append("")

        # Section 2: Research Analysis (Tool Results)
        user_parts.append("## RESEARCH ANALYSIS")
        user_parts.append("")
        user_parts.append("This section contains information gathered from research tools about the asset.")
        user_parts.append("")

        if state.tool_results:
            # Show lineage results
            if "lineage" in state.tool_results:
                lineage = state.tool_results["lineage"]
                user_parts.append("### Data Lineage")
                if lineage.get("available"):
                    user_parts.append(f"**Upstream Sources**: {', '.join(lineage.get('upstream', []))}")
                    user_parts.append(f"**Downstream Consumers**: {', '.join(lineage.get('downstream', []))}")
                    user_parts.append("")
                    user_parts.append("Use this lineage information to understand how data flows through this asset")
                    user_parts.append("and whether the asset is part of a restricted data pipeline.")
                else:
                    user_parts.append(f"*{lineage.get('message', 'Not available')}*")
                user_parts.append("")

            # Show metadata results
            if "metadata" in state.tool_results:
                metadata = state.tool_results["metadata"]
                user_parts.append("### Asset Metadata")
                if metadata.get("available"):
                    user_parts.append(f"**Description**: {metadata.get('description', 'N/A')}")
                    if metadata.get("fields"):
                        user_parts.append("**Fields**:")
                        for field in metadata.get("fields", []):
                            user_parts.append(f"  - {field['name']}: {field.get('type', 'unknown')} - {field.get('description', '')}")
                    user_parts.append("")
                    user_parts.append("Use this metadata to understand what data the asset contains")
                    user_parts.append("and whether it processes sensitive information.")
                else:
                    user_parts.append(f"*{metadata.get('message', 'Not available')}*")
                user_parts.append("")

            # Show classification results
            if "data_classification" in state.tool_results:
                classification = state.tool_results["data_classification"]
                user_parts.append("### Data Classification")
                if classification.get("available"):
                    user_parts.append(f"**Contains PII**: {classification.get('contains_pii', 'Unknown')}")
                    user_parts.append(f"**Sensitivity Level**: {classification.get('sensitivity', 'Unknown')}")
                    user_parts.append("")
                    user_parts.append("Use this classification to determine if the asset contains")
                    user_parts.append("sensitive data subject to the commitment requirements.")
                else:
                    user_parts.append(f"*{classification.get('message', 'Not available')}*")
                user_parts.append("")
        else:
            user_parts.append("*No tool research results available.*")
            user_parts.append("")

        user_parts.append("---")
        user_parts.append("")

        # Section 3: Prior Decisions
        user_parts.append("## PRIOR DECISIONS")
        user_parts.append("")
        user_parts.append("These are similar scoping decisions made previously. Learn from these patterns to maintain consistency.")
        user_parts.append("")

        if state.similar_decisions:
            user_parts.append(f"**Found {len(state.similar_decisions)} similar prior decisions:**")
            user_parts.append("")

            for idx, decision in enumerate(state.similar_decisions):
                user_parts.append(f"### Prior Decision {idx + 1}")
                user_parts.append(f"**Decision ID**: `{decision['decision_id']}`")
                user_parts.append(f"**Similar Asset**: `{decision['asset_uri']}`")
                user_parts.append(f"**Similarity Score**: {decision['similarity']:.3f} (0.0 = unrelated, 1.0 = identical)")
                user_parts.append(f"**Decision**: {decision['decision']}")
                user_parts.append(f"**Confidence**: {decision['confidence_level']} ({decision['confidence_score']:.2f})")
                user_parts.append(f"**Reasoning**:")
                user_parts.append(f"```")
                user_parts.append(decision['reasoning'][:500])  # Truncate long reasoning
                if len(decision['reasoning']) > 500:
                    user_parts.append("... [truncated]")
                user_parts.append(f"```")

                # Show commitment references if available
                if decision.get('commitment_references'):
                    user_parts.append(f"**Referenced Chunks**: {', '.join([ref['chunk_id'] for ref in decision['commitment_references'][:3]])}")

                user_parts.append(f"**Date**: {decision['created_at']}")
                user_parts.append("")
        else:
            user_parts.append("*No similar prior decisions found.*")
            user_parts.append("")
            user_parts.append("This may be a novel asset type or the first decision for this commitment.")
            user_parts.append("")

        user_parts.append("---")
        user_parts.append("")

        # Section 4: Human in the Loop Feedback
        user_parts.append("## HUMAN IN THE LOOP FEEDBACK")
        user_parts.append("")
        user_parts.append("⚠️ **CRITICAL**: Human feedback is the most authoritative signal. When humans correct decisions,")
        user_parts.append("their reasoning should heavily influence your decision on similar assets.")
        user_parts.append("")

        if state.similar_feedback:
            # Count feedback with human input
            feedback_with_corrections = [f for f in state.similar_feedback if f.get('human_reason')]

            if feedback_with_corrections:
                user_parts.append(f"**Found {len(feedback_with_corrections)} human feedback entries:**")
                user_parts.append("")

                for idx, feedback in enumerate(feedback_with_corrections):
                    rating_symbol = "✅" if feedback['rating'] == 'up' else "❌"
                    rating_text = "VALIDATED" if feedback['rating'] == 'up' else "CORRECTED"

                    user_parts.append(f"### Human Feedback {idx + 1} - {rating_symbol} {rating_text}")
                    user_parts.append(f"**On Asset**: `{feedback['asset_uri']}`")
                    user_parts.append(f"**Agent Said**: {feedback['decision']}")
                    user_parts.append(f"**Human Assessment**: {rating_text}")
                    user_parts.append(f"**Human Reason**:")
                    user_parts.append(f"```")
                    user_parts.append(feedback['human_reason'])
                    user_parts.append(f"```")

                    if feedback.get('human_correction'):
                        user_parts.append(f"**Human Correction**:")
                        user_parts.append(f"```")
                        user_parts.append(feedback['human_correction'])
                        user_parts.append(f"```")

                    user_parts.append(f"**Similarity to Current Asset**: {feedback['similarity']:.3f}")
                    user_parts.append("")
                    user_parts.append("**How to use this feedback**:")
                    if feedback['rating'] == 'up':
                        user_parts.append(f"- The agent's reasoning was correct. Apply similar logic to this asset if characteristics match.")
                    else:
                        user_parts.append(f"- The agent's decision was incorrect. Learn from the human's correction to avoid the same mistake.")
                    user_parts.append("")
            else:
                user_parts.append("*No human feedback available for similar decisions.*")
                user_parts.append("")
        else:
            user_parts.append("*No prior decisions available, therefore no human feedback.*")
            user_parts.append("")

        user_parts.append("---")
        user_parts.append("")

        # Confidence context
        if state.confidence:
            user_parts.append("## CONFIDENCE CONTEXT")
            user_parts.append("")
            user_parts.append(f"**Pre-calculated Confidence Level**: {state.confidence.level}")
            user_parts.append(f"**Confidence Score**: {state.confidence.score:.2f}")
            user_parts.append(f"**Reasoning**: {state.confidence.reasoning}")
            user_parts.append("")
            if state.confidence.level == "insufficient":
                user_parts.append("⚠️ **INSUFFICIENT CONFIDENCE WARNING**")
                user_parts.append("")
                user_parts.append("The system has determined there is insufficient data to make a confident decision.")
                user_parts.append("You should strongly consider responding with decision='insufficient-data' unless you")
                user_parts.append("can identify clear evidence from the commitment language or human feedback.")
                user_parts.append("")
            user_parts.append("---")
            user_parts.append("")

        # Final task
        user_parts.append("## YOUR TASK")
        user_parts.append("")
        user_parts.append(f"Determine whether the asset **`{state.asset_uri}`** is:")
        user_parts.append("")
        user_parts.append("- **IN-SCOPE**: The asset processes sensitive data covered by this commitment and is within allowed uses")
        user_parts.append("- **OUT-OF-SCOPE**: The asset is outside the commitment boundary (prohibited use, doesn't process sensitive data, etc.)")
        user_parts.append("- **INSUFFICIENT-DATA**: You cannot make a confident decision with the available information")
        user_parts.append("")
        user_parts.append("**Requirements**:")
        user_parts.append("")
        user_parts.append("1. Cite specific commitment chunks by ID")
        user_parts.append("2. Reference prior decisions and explain their influence")
        user_parts.append("3. Explain how human feedback guided your reasoning")
        user_parts.append("4. If uncertain, choose 'insufficient-data' and specify what information is needed")
        user_parts.append("5. Provide detailed evidence and reasoning")
        user_parts.append("")
        user_parts.append("Respond in the JSON format specified in the system prompt.")
        user_parts.append("")

        user_prompt = "\n".join(user_parts)

        # Store in telemetry
        state.telemetry_data["prompt_construction"] = {
            "system_prompt_length": len(system_prompt),
            "user_prompt_length": len(user_prompt),
            "rag_chunks_included": len(state.rag_chunks),
            "similar_decisions_included": len(state.similar_decisions),
            "feedback_examples_included": len(state.similar_feedback),
            "tool_results_included": len(state.tool_results),
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
