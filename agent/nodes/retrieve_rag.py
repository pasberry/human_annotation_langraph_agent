"""Node for retrieving relevant commitment documentation via RAG."""
import time

from storage import commitment_search_service, db, embedding_service, rag_service
from storage.schemas import AgentState, RAGContext


def retrieve_rag_node(state: AgentState) -> AgentState:
    """
    Retrieve relevant commitment documentation chunks.

    Supports two modes:
    1. Specific commitment (commitment_id): Retrieves chunks from one commitment
    2. Natural language query (commitment_query): Searches for relevant commitments,
       then retrieves chunks from all matching commitments

    Args:
        state: Current agent state

    Returns:
        Updated state with RAG chunks and context
    """
    start = time.time()

    try:
        commitments_to_search = []

        # Mode 1: Specific commitment ID
        if state.commitment_id:
            commitment = db.get_commitment(state.commitment_id)
            if not commitment:
                # Try by name
                commitment = db.get_commitment_by_name(state.commitment_id)

            if not commitment:
                state.errors.append(f"Commitment not found: {state.commitment_id}")
                return state

            state.commitment = commitment
            state.commitment_name = commitment.name
            commitments_to_search = [commitment]

        # Mode 2: Natural language commitment query
        elif state.commitment_query:
            # Search for relevant commitments
            commitments_to_search = commitment_search_service.search_commitments(
                query=state.commitment_query,
                top_k=3,  # Get top 3 most relevant commitments
                score_threshold=0.6
            )

            if not commitments_to_search:
                state.errors.append(f"No commitments found matching: '{state.commitment_query}'")
                return state

            # Set primary commitment and related commitments
            state.commitment = commitments_to_search[0]  # Most relevant
            state.related_commitments = commitments_to_search[1:] if len(commitments_to_search) > 1 else []
            state.commitment_name = f"{state.commitment.name} (+ {len(state.related_commitments)} related)"

        else:
            state.errors.append("Must provide either commitment_id or commitment_query")
            return state

        # Build query text for embedding
        commitment_names = ", ".join([c.name for c in commitments_to_search])
        query_text = f"Asset: {state.asset_uri}. Commitments: {commitment_names}. Determine if asset is in-scope or out-of-scope."

        # Generate query embedding if not already done
        if not state.query_embedding:
            state.query_embedding = embedding_service.embed_text(query_text)

        # Retrieve relevant chunks from ALL relevant commitments
        all_chunks = []
        all_scores = []

        for commitment in commitments_to_search:
            rag_result = rag_service.get_commitment_context(
                query_embedding=state.query_embedding,
                commitment_id=commitment.id
            )
            all_chunks.extend(rag_result["chunks"])
            all_scores.extend(rag_result["scores"])

        # Sort by score and take top chunks
        if all_chunks:
            # Combine chunks and scores, sort by score
            chunk_score_pairs = list(zip(all_chunks, all_scores))
            chunk_score_pairs.sort(key=lambda x: x[1], reverse=True)

            # Take top chunks across all commitments
            top_k = min(len(chunk_score_pairs), 10)  # Max 10 chunks total
            all_chunks = [pair[0] for pair in chunk_score_pairs[:top_k]]
            all_scores = [pair[1] for pair in chunk_score_pairs[:top_k]]

        state.rag_chunks = all_chunks
        state.rag_context = RAGContext(
            chunks_retrieved=len(all_chunks),
            chunk_ids=[chunk.id for chunk in all_chunks],
            avg_similarity=sum(all_scores) / len(all_scores) if all_scores else 0.0,
            top_similarity=max(all_scores) if all_scores else 0.0
        )

        # Track telemetry
        state.telemetry_data["rag_retrieval"] = {
            "mode": "commitment_id" if state.commitment_id else "commitment_query",
            "commitment_query": state.commitment_query,
            "commitments_searched": len(commitments_to_search),
            "commitment_names": [c.name for c in commitments_to_search],
            "query_embedding_dim": len(state.query_embedding),
            "chunks_retrieved": len(all_chunks),
            "avg_similarity": state.rag_context.avg_similarity,
            "top_similarity": state.rag_context.top_similarity,
            "time_ms": (time.time() - start) * 1000
        }

    except Exception as e:
        state.errors.append(f"RAG retrieval error: {str(e)}")
        state.telemetry_data["rag_retrieval"] = {
            "error": str(e),
            "time_ms": (time.time() - start) * 1000
        }

    return state
