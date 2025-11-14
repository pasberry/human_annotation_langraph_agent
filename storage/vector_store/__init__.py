"""Vector store abstraction layer."""
from storage.vector_store.base import VectorStore
from storage.vector_store.factory import get_vector_store

__all__ = ["VectorStore", "get_vector_store"]
