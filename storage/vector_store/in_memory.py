"""In-memory vector store implementation."""
import numpy as np
from typing import List, Optional, Any

from storage.vector_store.base import VectorStore, VectorDocument, SimilarityResult


class InMemoryVectorStore(VectorStore):
    """
    In-memory vector store using numpy for similarity search.

    Good for:
    - Local development
    - Testing
    - Small datasets
    - No external dependencies
    """

    def __init__(self):
        """Initialize in-memory store."""
        self.documents: dict[str, VectorDocument] = {}

    def add_documents(self, documents: List[VectorDocument]) -> None:
        """Add documents to the in-memory store."""
        for doc in documents:
            self.documents[doc.id] = doc

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(v1, v2) / (norm1 * norm2))

    def _matches_filter(self, metadata: dict[str, Any], filter_metadata: dict[str, Any]) -> bool:
        """Check if metadata matches filter criteria."""
        for key, value in filter_metadata.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[dict[str, Any]] = None,
        score_threshold: Optional[float] = None
    ) -> List[SimilarityResult]:
        """Search for similar documents using cosine similarity."""
        # Filter documents by metadata if needed
        candidates = []
        for doc in self.documents.values():
            if filter_metadata and not self._matches_filter(doc.metadata, filter_metadata):
                continue
            candidates.append(doc)

        # Calculate similarities
        similarities = []
        for doc in candidates:
            score = self._cosine_similarity(query_embedding, doc.embedding)

            # Apply score threshold
            if score_threshold and score < score_threshold:
                continue

            similarities.append((doc, score))

        # Sort by score descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Take top k
        top_results = similarities[:top_k]

        # Convert to SimilarityResult
        return [
            SimilarityResult(
                id=doc.id,
                text=doc.text,
                score=score,
                metadata=doc.metadata
            )
            for doc, score in top_results
        ]

    def delete_by_id(self, document_id: str) -> None:
        """Delete a document by ID."""
        if document_id in self.documents:
            del self.documents[document_id]

    def delete_by_metadata(self, filter_metadata: dict[str, Any]) -> None:
        """Delete documents matching metadata filter."""
        to_delete = [
            doc_id for doc_id, doc in self.documents.items()
            if self._matches_filter(doc.metadata, filter_metadata)
        ]
        for doc_id in to_delete:
            del self.documents[doc_id]

    def get_by_id(self, document_id: str) -> Optional[VectorDocument]:
        """Get a document by ID."""
        return self.documents.get(document_id)

    def count(self, filter_metadata: Optional[dict[str, Any]] = None) -> int:
        """Count documents in the store."""
        if not filter_metadata:
            return len(self.documents)

        return sum(
            1 for doc in self.documents.values()
            if self._matches_filter(doc.metadata, filter_metadata)
        )

    def clear(self) -> None:
        """Clear all documents."""
        self.documents.clear()
