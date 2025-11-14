"""ChromaDB vector store implementation."""
from typing import List, Optional, Any
import json

from storage.vector_store.base import VectorStore, VectorDocument, SimilarityResult


class ChromaVectorStore(VectorStore):
    """
    ChromaDB vector store implementation.

    Good for:
    - Local development with persistence
    - Medium-sized datasets
    - Self-hosted deployments
    - Easy setup
    """

    def __init__(self, collection_name: str = "evidencing_agent", persist_directory: Optional[str] = None):
        """
        Initialize ChromaDB store.

        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist data (None for in-memory)
        """
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise ImportError(
                "ChromaDB not installed. Install with: pip install chromadb"
            )

        # Initialize client
        if persist_directory:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
        else:
            self.client = chromadb.Client(
                settings=Settings(anonymized_telemetry=False)
            )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )

    def add_documents(self, documents: List[VectorDocument]) -> None:
        """Add documents to ChromaDB."""
        if not documents:
            return

        ids = [doc.id for doc in documents]
        embeddings = [doc.embedding for doc in documents]
        texts = [doc.text for doc in documents]
        metadatas = [self._serialize_metadata(doc.metadata) for doc in documents]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

    def _serialize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Serialize metadata for ChromaDB (only supports simple types)."""
        serialized = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                serialized[key] = value
            else:
                # Convert complex types to JSON string
                serialized[key] = json.dumps(value)
        return serialized

    def _deserialize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Deserialize metadata from ChromaDB."""
        deserialized = {}
        for key, value in metadata.items():
            if isinstance(value, str):
                try:
                    # Try to parse JSON
                    deserialized[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # Keep as string if not JSON
                    deserialized[key] = value
            else:
                deserialized[key] = value
        return deserialized

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[dict[str, Any]] = None,
        score_threshold: Optional[float] = None
    ) -> List[SimilarityResult]:
        """Search for similar documents in ChromaDB."""
        # Build where clause for metadata filtering
        where = None
        if filter_metadata:
            where = self._build_where_clause(filter_metadata)

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where
        )

        # Convert to SimilarityResult
        similarity_results = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                # ChromaDB returns distance, convert to similarity score
                # For cosine distance: similarity = 1 - distance
                distance = results['distances'][0][i] if results['distances'] else 0
                score = 1.0 - distance

                # Apply score threshold
                if score_threshold and score < score_threshold:
                    continue

                text = results['documents'][0][i] if results['documents'] else ""
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}

                similarity_results.append(
                    SimilarityResult(
                        id=doc_id,
                        text=text,
                        score=score,
                        metadata=self._deserialize_metadata(metadata)
                    )
                )

        return similarity_results

    def _build_where_clause(self, filter_metadata: dict[str, Any]) -> dict[str, Any]:
        """Build ChromaDB where clause from metadata filter."""
        # Simple equality filters
        where = {}
        for key, value in filter_metadata.items():
            if isinstance(value, (str, int, float, bool)):
                where[key] = value
            else:
                where[key] = json.dumps(value)
        return where

    def delete_by_id(self, document_id: str) -> None:
        """Delete a document by ID."""
        try:
            self.collection.delete(ids=[document_id])
        except Exception:
            # Document may not exist, ignore
            pass

    def delete_by_metadata(self, filter_metadata: dict[str, Any]) -> None:
        """Delete documents matching metadata filter."""
        where = self._build_where_clause(filter_metadata)
        self.collection.delete(where=where)

    def get_by_id(self, document_id: str) -> Optional[VectorDocument]:
        """Get a document by ID."""
        try:
            results = self.collection.get(ids=[document_id], include=["embeddings", "documents", "metadatas"])

            if results and results['ids']:
                return VectorDocument(
                    id=results['ids'][0],
                    text=results['documents'][0] if results['documents'] else "",
                    embedding=results['embeddings'][0] if results['embeddings'] else [],
                    metadata=self._deserialize_metadata(results['metadatas'][0]) if results['metadatas'] else {}
                )
        except Exception:
            pass

        return None

    def count(self, filter_metadata: Optional[dict[str, Any]] = None) -> int:
        """Count documents in the store."""
        if filter_metadata:
            where = self._build_where_clause(filter_metadata)
            results = self.collection.get(where=where)
            return len(results['ids']) if results and results['ids'] else 0
        else:
            return self.collection.count()

    def clear(self) -> None:
        """Clear all documents."""
        # Delete the collection and recreate it
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine"}
        )
