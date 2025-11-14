"""Abstract base class for vector stores."""
from abc import ABC, abstractmethod
from typing import Any, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class VectorDocument:
    """Document with vector embedding."""

    id: str
    text: str
    embedding: List[float]
    metadata: dict[str, Any]


@dataclass
class SimilarityResult:
    """Result from similarity search."""

    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class VectorStore(ABC):
    """Abstract base class for vector database implementations."""

    @abstractmethod
    def add_documents(self, documents: List[VectorDocument]) -> None:
        """
        Add documents with embeddings to the vector store.

        Args:
            documents: List of documents with embeddings and metadata
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[dict[str, Any]] = None,
        score_threshold: Optional[float] = None
    ) -> List[SimilarityResult]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filter_metadata: Metadata filters to apply
            score_threshold: Minimum similarity score

        Returns:
            List of similar documents with scores
        """
        pass

    @abstractmethod
    def delete_by_id(self, document_id: str) -> None:
        """
        Delete a document by ID.

        Args:
            document_id: ID of document to delete
        """
        pass

    @abstractmethod
    def delete_by_metadata(self, filter_metadata: dict[str, Any]) -> None:
        """
        Delete documents matching metadata filter.

        Args:
            filter_metadata: Metadata filter for deletion
        """
        pass

    @abstractmethod
    def get_by_id(self, document_id: str) -> Optional[VectorDocument]:
        """
        Get a document by ID.

        Args:
            document_id: ID of document to retrieve

        Returns:
            Document if found, None otherwise
        """
        pass

    @abstractmethod
    def count(self, filter_metadata: Optional[dict[str, Any]] = None) -> int:
        """
        Count documents in the store.

        Args:
            filter_metadata: Optional metadata filter

        Returns:
            Number of documents
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all documents from the vector store."""
        pass
