"""Node for retrieving relevant commitment documentation via RAG."""
import time

from storage import db, embedding_service, rag_service
from storage.schemas import AgentState, RAGContext


def retrieve_rag_node(state: AgentState) -> AgentState:
    """
    Retrieve relevant commitment documentation chunks.

    Args:
        state: Current agent state

    Returns:
        Updated state with RAG chunks and context
    """
    start = time.time()

    try:
        # Get commitment from database
        commitment = db.get_commitment(state.commitment_id)
        if not commitment:
            # Try by name
            commitment = db.get_commitment_by_name(state.commitment_id)

        if not commitment:
            state.errors.append(f"Commitment not found: {state.commitment_id}")
            return state

        state.commitment = commitment
        state.commitment_name = commitment.name

        # Build query text for embedding
        query_text = f"Asset: {state.asset_uri}. Commitment: {commitment.name}. Determine if asset is in-scope or out-of-scope."

        # Generate query embedding if not already done
        if not state.query_embedding:
            state.query_embedding = embedding_service.embed_text(query_text)

        # Retrieve relevant chunks
        rag_result = rag_service.get_commitment_context(
            query_embedding=state.query_embedding,
            commitment_id=commitment.id
        )

        state.rag_chunks = rag_result["chunks"]
        state.rag_context = RAGContext(
            chunks_retrieved=rag_result["num_chunks"],
            chunk_ids=[chunk.id for chunk in rag_result["chunks"]],
            avg_similarity=rag_result["avg_similarity"],
            top_similarity=rag_result["top_similarity"]
        )

        # Track telemetry
        state.telemetry_data["rag_retrieval"] = {
            "commitment_id": commitment.id,
            "commitment_name": commitment.name,
            "query_embedding_dim": len(state.query_embedding),
            "chunks_retrieved": rag_result["num_chunks"],
            "avg_similarity": rag_result["avg_similarity"],
            "top_similarity": rag_result["top_similarity"],
            "scores": rag_result["scores"],
            "time_ms": (time.time() - start) * 1000
        }

    except Exception as e:
        state.errors.append(f"RAG retrieval error: {str(e)}")
        state.telemetry_data["rag_retrieval"] = {
            "error": str(e),
            "time_ms": (time.time() - start) * 1000
        }

    return state
