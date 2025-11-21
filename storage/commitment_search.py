"""Service for searching and managing commitments."""
from storage.schemas import Commitment
from storage.vector_store.base import VectorDocument


class CommitmentSearchService:
    """Service for searching commitments by natural language queries."""

    def __init__(self, db=None, vector_store=None, embedding_service=None):
        """Initialize with optional service instances (for testing)."""
        self._db = db
        self._vector_store = vector_store
        self._embedding_service = embedding_service

    @property
    def db(self):
        """Lazy load database instance."""
        if self._db is None:
            from storage.database import db
            self._db = db
        return self._db

    @property
    def vector_store(self):
        """Lazy load vector store instance."""
        if self._vector_store is None:
            from storage.vector_store import vector_store
            self._vector_store = vector_store
        return self._vector_store

    @property
    def embedding_service(self):
        """Lazy load embedding service instance."""
        if self._embedding_service is None:
            from storage.embeddings import embedding_service
            self._embedding_service = embedding_service
        return self._embedding_service

    def search_commitments(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: float = 0.6
    ) -> list[Commitment]:
        """
        Search for commitments using natural language query.

        Args:
            query: Natural language description (e.g., "no user data for ads")
            top_k: Number of commitments to return
            score_threshold: Minimum similarity score

        Returns:
            List of matching commitments, ordered by relevance

        Example:
            >>> service.search_commitments("no ads commitments", top_k=3)
            [
                Commitment(name="User Data - No Advertising", ...),
                Commitment(name="Minor Data Protection - No Ad Training", ...),
                Commitment(name="Telemarketing Restrictions", ...)
            ]
        """
        # Generate embedding for the query
        query_embedding = self.embedding_service.embed_text(query)

        # Search vector store for commitment summaries
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Get more candidates
            filter_metadata={"type": "commitment_summary"},
            score_threshold=score_threshold
        )

        if not results:
            return []

        # Get full commitment objects from database
        commitments = []
        for result in results[:top_k]:
            commitment_id = result.metadata.get("commitment_id")
            if commitment_id:
                commitment = self.db.get_commitment(commitment_id)
                if commitment:
                    commitments.append(commitment)

        return commitments

    def store_commitment_summary(self, commitment: Commitment) -> None:
        """
        Store commitment summary in vector DB for search.

        This creates a searchable entry combining the commitment name
        and description (which should be LLM-generated for rich semantic content).

        The description should capture:
        - What data/assets are governed
        - Key prohibitions and permissions
        - Relevant keywords for search

        Args:
            commitment: The commitment to make searchable
        """
        # Build searchable text from name + LLM description
        summary_text = f"{commitment.name}"
        if commitment.description:
            summary_text += f". {commitment.description}"

        # Generate embedding
        embedding = self.embedding_service.embed_text(summary_text)

        # Store in vector DB
        vector_doc = VectorDocument(
            id=f"commitment_summary_{commitment.id}",
            text=summary_text,
            embedding=embedding,
            metadata={
                "type": "commitment_summary",
                "commitment_id": commitment.id,
                "name": commitment.name
            }
        )

        self.vector_store.add_documents([vector_doc])

    def delete_commitment_summary(self, commitment_id: str) -> None:
        """
        Delete commitment summary from vector store.

        Args:
            commitment_id: ID of commitment to remove
        """
        self.vector_store.delete_by_id(f"commitment_summary_{commitment_id}")


# Global service instance
commitment_search_service = CommitmentSearchService()
