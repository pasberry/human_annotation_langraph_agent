"""Node for calling the LLM to generate decision."""
import json
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

from config import settings
from storage.schemas import AgentState, ScopingResponse


def get_llm():
    """Get configured LLM instance."""
    if settings.llm_provider == "openai":
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.openai_api_key,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
    elif settings.llm_provider == "ollama":
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            base_url=settings.llm_base_url,
            api_key="ollama",  # Ollama doesn't need a real API key
            model_kwargs={"format": "json"}
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def llm_call_node(state: AgentState) -> AgentState:
    """
    Call the LLM to generate a scoping decision.

    Args:
        state: Current agent state with prompts built

    Returns:
        Updated state with LLM response
    """
    start = time.time()

    try:
        # Get prompts from telemetry
        prompts = state.telemetry_data.get("prompts", {})
        system_prompt = prompts.get("system", "")
        user_prompt = prompts.get("user", "")

        if not system_prompt or not user_prompt:
            raise ValueError("Prompts not found in state. build_prompt_node must run first.")

        # Get LLM instance
        llm = get_llm()

        # Create messages
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        # Call LLM
        llm_start = time.time()
        response = llm.invoke(messages)
        llm_time = (time.time() - llm_start) * 1000

        # Parse JSON response
        response_text = response.content
        response_json = json.loads(response_text)

        # Validate and create ScopingResponse
        scoping_response = ScopingResponse(**response_json)
        state.response = scoping_response

        # Track telemetry
        usage = getattr(response, "usage_metadata", None) or {}
        state.telemetry_data["llm_call"] = {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "response_time_ms": llm_time,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "decision": scoping_response.decision,
            "confidence_level": scoping_response.confidence_level,
            "confidence_score": scoping_response.confidence_score,
            "time_ms": (time.time() - start) * 1000
        }

    except json.JSONDecodeError as e:
        error_msg = f"LLM response is not valid JSON: {str(e)}"
        state.errors.append(error_msg)
        state.telemetry_data["llm_call"] = {
            "error": error_msg,
            "raw_response": response_text if "response_text" in locals() else None,
            "time_ms": (time.time() - start) * 1000
        }

    except Exception as e:
        state.errors.append(f"LLM call error: {str(e)}")
        state.telemetry_data["llm_call"] = {
            "error": str(e),
            "time_ms": (time.time() - start) * 1000
        }

    return state
