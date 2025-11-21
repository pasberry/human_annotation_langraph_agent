"""Vector store abstraction layer."""
from storage.vector_store.base import VectorStore, VectorDocument, SimilarityResult
from storage.vector_store.factory import get_vector_store, get_vector_store_from_config
from config import settings

# Global vector store instance
vector_store = get_vector_store_from_config(settings)

__all__ = ["VectorStore", "VectorDocument", "SimilarityResult", "get_vector_store", "vector_store"]
