"""RAG system for commitment document retrieval."""
from typing import List, Optional

from config import settings
from storage.database import db
from storage.embeddings import embedding_service
from storage.schemas import Commitment, CommitmentChunk
from storage.vector_store.factory import get_vector_store_from_config
from storage.vector_store.base import VectorDocument, SimilarityResult


class RAGService:
    """Service for chunking and retrieving commitment documents using vector stores."""

    def __init__(self, vector_store=None):
        """
        Initialize RAG service.

        Args:
            vector_store: Optional vector store instance (defaults to config-based store)
        """
        self.chunk_size = settings.rag_chunk_size
        self.chunk_overlap = settings.rag_chunk_overlap
        self.top_k = settings.rag_top_k

        # Initialize vector store
        if vector_store is None:
            self.vector_store = get_vector_store_from_config(settings)
        else:
            self.vector_store = vector_store

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
        Process a commitment document: chunk it and store with embeddings in vector store.

        The database stores chunk metadata (text, IDs), while the vector store
        handles embeddings for similarity search.

        Args:
            commitment: Commitment to process

        Returns:
            List of created chunks
        """
        # Combine doc text and scoping criteria for chunking
        full_text = f"{commitment.doc_text}\n\n"
        if commitment.scoping_criteria:
            full_text += f"Scoping Criteria:\n{commitment.scoping_criteria}"

        # Chunk the text
        text_chunks = self.chunk_text(full_text)

        # Generate embeddings
        embeddings = embedding_service.embed_texts(text_chunks)

        # Create chunk objects (without embeddings for database)
        chunks = [
            CommitmentChunk(
                commitment_id=commitment.id,
                chunk_text=text,
                chunk_embedding=[],  # Don't store in DB anymore
                chunk_index=idx
            )
            for idx, text in enumerate(text_chunks)
        ]

        # Store metadata in database
        db.add_commitment_chunks(chunks)

        # Store vectors in vector store
        vector_docs = [
            VectorDocument(
                id=chunk.id,
                text=chunk.chunk_text,
                embedding=embedding,
                metadata={
                    "commitment_id": commitment.id,
                    "commitment_name": commitment.name,
                    "chunk_index": chunk.chunk_index,
                    "type": "commitment_chunk"
                }
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        self.vector_store.add_documents(vector_docs)

        return chunks

    def retrieve_relevant_chunks(
        self,
        query_embedding: list[float],
        commitment_id: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> tuple[list[CommitmentChunk], list[float]]:
        """
        Retrieve most relevant commitment chunks using vector similarity search.

        Args:
            query_embedding: Query embedding vector
            commitment_id: Optional commitment ID to filter by
            top_k: Number of chunks to retrieve (defaults to config)

        Returns:
            Tuple of (chunks, similarity_scores)
        """
        top_k = top_k or self.top_k

        # Build metadata filter
        filter_metadata = {"type": "commitment_chunk"}
        if commitment_id:
            filter_metadata["commitment_id"] = commitment_id

        # Search vector store
        results: List[SimilarityResult] = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
            score_threshold=0.0  # No threshold for RAG, just get top-k
        )

        if not results:
            return [], []

        # Fetch full chunk metadata from database
        chunk_ids = [r.id for r in results]
        chunks_dict = {}

        # Get chunks from database
        if commitment_id:
            db_chunks = db.get_commitment_chunks(commitment_id)
            chunks_dict = {chunk.id: chunk for chunk in db_chunks if chunk.id in chunk_ids}
        else:
            # Get all chunks and filter by IDs
            all_chunks = db.get_all_chunks()
            chunks_dict = {chunk.id: chunk for chunk in all_chunks if chunk.id in chunk_ids}

        # Build result maintaining search order
        result_chunks = []
        scores = []

        for result in results:
            if result.id in chunks_dict:
                result_chunks.append(chunks_dict[result.id])
                scores.append(result.score)

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

    def delete_commitment_vectors(self, commitment_id: str) -> None:
        """
        Delete all vectors for a commitment from the vector store.

        Args:
            commitment_id: ID of commitment to delete
        """
        self.vector_store.delete_by_metadata(
            {"type": "commitment_chunk", "commitment_id": commitment_id}
        )


# Global RAG service instance
rag_service = RAGService()
