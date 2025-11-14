"""RAG system for commitment document retrieval."""
from typing import List

from config import settings
from storage.database import db
from storage.embeddings import embedding_service
from storage.schemas import Commitment, CommitmentChunk


class RAGService:
    """Service for chunking and retrieving commitment documents."""

    def __init__(self):
        """Initialize RAG service."""
        self.chunk_size = settings.rag_chunk_size
        self.chunk_overlap = settings.rag_chunk_overlap
        self.top_k = settings.rag_top_k

    def chunk_text(self, text: str) -> list[str]:
        """
        Chunk text into overlapping segments.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # Don't add tiny chunks at the end
            if len(chunk) > 50:
                chunks.append(chunk)

            start += (self.chunk_size - self.chunk_overlap)

        return chunks

    def process_and_store_commitment(self, commitment: Commitment) -> list[CommitmentChunk]:
        """
        Process a commitment document: chunk it and store with embeddings.

        Args:
            commitment: Commitment to process

        Returns:
            List of created chunks
        """
        # Combine legal text and scoping criteria for chunking
        full_text = f"{commitment.legal_text}\n\n"
        if commitment.scoping_criteria:
            full_text += f"Scoping Criteria:\n{commitment.scoping_criteria}"

        # Chunk the text
        text_chunks = self.chunk_text(full_text)

        # Generate embeddings and create chunk objects
        embeddings = embedding_service.embed_texts(text_chunks)

        chunks = [
            CommitmentChunk(
                commitment_id=commitment.id,
                chunk_text=text,
                chunk_embedding=embedding,
                chunk_index=idx
            )
            for idx, (text, embedding) in enumerate(zip(text_chunks, embeddings))
        ]

        # Store in database
        db.add_commitment_chunks(chunks)

        return chunks

    def retrieve_relevant_chunks(
        self,
        query_embedding: list[float],
        commitment_id: str | None = None,
        top_k: int | None = None
    ) -> tuple[list[CommitmentChunk], list[float]]:
        """
        Retrieve most relevant commitment chunks for a query.

        Args:
            query_embedding: Query embedding vector
            commitment_id: Optional commitment ID to filter by
            top_k: Number of chunks to retrieve (defaults to config)

        Returns:
            Tuple of (chunks, similarity_scores)
        """
        top_k = top_k or self.top_k

        # Get chunks to search
        if commitment_id:
            chunks = db.get_commitment_chunks(commitment_id)
        else:
            chunks = db.get_all_chunks()

        if not chunks:
            return [], []

        # Extract embeddings
        chunk_embeddings = [chunk.chunk_embedding for chunk in chunks]

        # Find most similar
        similar_indices = embedding_service.find_most_similar(
            query_embedding=query_embedding,
            candidate_embeddings=chunk_embeddings,
            top_k=top_k,
            threshold=0.0  # No threshold for RAG, just get top-k
        )

        # Return chunks and scores
        result_chunks = [chunks[idx] for idx, _ in similar_indices]
        scores = [score for _, score in similar_indices]

        return result_chunks, scores

    def get_commitment_context(
        self,
        query_embedding: list[float],
        commitment_id: str
    ) -> dict:
        """
        Get RAG context for a specific commitment.

        Returns dict with chunks and metadata.
        """
        chunks, scores = self.retrieve_relevant_chunks(
            query_embedding=query_embedding,
            commitment_id=commitment_id
        )

        return {
            "chunks": chunks,
            "scores": scores,
            "avg_similarity": sum(scores) / len(scores) if scores else 0.0,
            "top_similarity": max(scores) if scores else 0.0,
            "num_chunks": len(chunks)
        }


# Global RAG service instance
rag_service = RAGService()
