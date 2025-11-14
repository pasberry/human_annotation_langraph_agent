"""Pinecone vector store implementation."""
from typing import List, Optional, Any
import json

from storage.vector_store.base import VectorStore, VectorDocument, SimilarityResult


class PineconeVectorStore(VectorStore):
    """
    Pinecone vector store implementation.

    Good for:
    - Production deployments
    - Large-scale datasets
    - Managed service (no infrastructure)
    - High performance
    """

    def __init__(
        self,
        api_key: str,
        index_name: str,
        environment: Optional[str] = None,
        namespace: str = "default"
    ):
        """
        Initialize Pinecone store.

        Args:
            api_key: Pinecone API key
            index_name: Name of the Pinecone index
            environment: Pinecone environment (e.g., 'us-west1-gcp')
            namespace: Namespace within the index
        """
        try:
            from pinecone import Pinecone, ServerlessSpec
        except ImportError:
            raise ImportError(
                "Pinecone not installed. Install with: pip install pinecone-client"
            )

        # Initialize Pinecone
        self.pc = Pinecone(api_key=api_key)

        # Get or create index
        self.index_name = index_name
        self.namespace = namespace

        # Check if index exists
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]

        if index_name not in existing_indexes:
            raise ValueError(
                f"Index '{index_name}' does not exist. "
                f"Please create it first with the appropriate dimension and metric. "
                f"Example: pc.create_index(name='{index_name}', dimension=384, metric='cosine', spec=ServerlessSpec(cloud='aws', region='us-east-1'))"
            )

        # Connect to index
        self.index = self.pc.Index(index_name)

    def add_documents(self, documents: List[VectorDocument]) -> None:
        """Add documents to Pinecone."""
        if not documents:
            return

        # Prepare vectors for upsert
        vectors = []
        for doc in documents:
            vectors.append({
                "id": doc.id,
                "values": doc.embedding,
                "metadata": {
                    **self._serialize_metadata(doc.metadata),
                    "_text": doc.text  # Store text in metadata
                }
            })

        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace=self.namespace)

    def _serialize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Serialize metadata for Pinecone."""
        serialized = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                serialized[key] = value
            elif isinstance(value, list):
                # Pinecone supports list of strings or numbers
                if all(isinstance(v, (str, int, float, bool)) for v in value):
                    serialized[key] = value
                else:
                    serialized[f"{key}_json"] = json.dumps(value)
            else:
                # Convert complex types to JSON string
                serialized[f"{key}_json"] = json.dumps(value)
        return serialized

    def _deserialize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Deserialize metadata from Pinecone."""
        deserialized = {}
        for key, value in metadata.items():
            if key == "_text":
                continue  # Skip internal text field

            if key.endswith("_json"):
                # Deserialize JSON fields
                original_key = key[:-5]  # Remove _json suffix
                try:
                    deserialized[original_key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    deserialized[original_key] = value
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
        """Search for similar documents in Pinecone."""
        # Build filter for metadata
        filter_dict = None
        if filter_metadata:
            filter_dict = self._build_filter(filter_metadata)

        # Query Pinecone
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=self.namespace,
            filter=filter_dict,
            include_metadata=True
        )

        # Convert to SimilarityResult
        similarity_results = []
        for match in results.matches:
            # Apply score threshold
            if score_threshold and match.score < score_threshold:
                continue

            metadata = match.metadata or {}
            text = metadata.pop("_text", "")

            similarity_results.append(
                SimilarityResult(
                    id=match.id,
                    text=text,
                    score=match.score,
                    metadata=self._deserialize_metadata(metadata)
                )
            )

        return similarity_results

    def _build_filter(self, filter_metadata: dict[str, Any]) -> dict[str, Any]:
        """Build Pinecone filter from metadata."""
        # Pinecone uses MongoDB-style filters
        filter_clauses = []

        for key, value in filter_metadata.items():
            if isinstance(value, (str, int, float, bool)):
                filter_clauses.append({key: {"$eq": value}})
            elif isinstance(value, list):
                filter_clauses.append({key: {"$in": value}})
            else:
                # For complex types, filter on JSON string
                filter_clauses.append({f"{key}_json": {"$eq": json.dumps(value)}})

        if len(filter_clauses) == 1:
            return filter_clauses[0]
        elif len(filter_clauses) > 1:
            return {"$and": filter_clauses}
        else:
            return {}

    def delete_by_id(self, document_id: str) -> None:
        """Delete a document by ID."""
        self.index.delete(ids=[document_id], namespace=self.namespace)

    def delete_by_metadata(self, filter_metadata: dict[str, Any]) -> None:
        """Delete documents matching metadata filter."""
        filter_dict = self._build_filter(filter_metadata)
        self.index.delete(filter=filter_dict, namespace=self.namespace)

    def get_by_id(self, document_id: str) -> Optional[VectorDocument]:
        """Get a document by ID."""
        results = self.index.fetch(ids=[document_id], namespace=self.namespace)

        if results.vectors and document_id in results.vectors:
            vector_data = results.vectors[document_id]
            metadata = vector_data.metadata or {}
            text = metadata.pop("_text", "")

            return VectorDocument(
                id=document_id,
                text=text,
                embedding=vector_data.values,
                metadata=self._deserialize_metadata(metadata)
            )

        return None

    def count(self, filter_metadata: Optional[dict[str, Any]] = None) -> int:
        """
        Count documents in the store.

        Note: Pinecone doesn't have a direct count API, so this queries
        and counts results. For large datasets, this may be expensive.
        """
        # Get index stats
        stats = self.index.describe_index_stats()

        if not filter_metadata:
            # Return total count for namespace
            if self.namespace in stats.namespaces:
                return stats.namespaces[self.namespace].vector_count
            return 0
        else:
            # For filtered count, we need to query with a dummy vector
            # This is expensive - consider caching or maintaining counts separately
            # Query with zero vector to get IDs
            dummy_vector = [0.0] * self.index.dimension
            filter_dict = self._build_filter(filter_metadata)

            results = self.index.query(
                vector=dummy_vector,
                top_k=10000,  # Max limit
                namespace=self.namespace,
                filter=filter_dict,
                include_metadata=False
            )

            return len(results.matches)

    def clear(self) -> None:
        """Clear all documents from the namespace."""
        self.index.delete(delete_all=True, namespace=self.namespace)
