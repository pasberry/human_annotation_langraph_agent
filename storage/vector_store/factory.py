"""Factory for creating vector store instances."""
from typing import Optional

from storage.vector_store.base import VectorStore


def get_vector_store(
    store_type: str = "in_memory",
    **kwargs
) -> VectorStore:
    """
    Factory function to create vector store instances.

    Args:
        store_type: Type of vector store ('in_memory', 'chroma', 'pinecone')
        **kwargs: Additional arguments for the specific store type

    Returns:
        VectorStore instance

    Examples:
        # In-memory (default)
        store = get_vector_store("in_memory")

        # ChromaDB with persistence
        store = get_vector_store(
            "chroma",
            collection_name="my_collection",
            persist_directory="./chroma_data"
        )

        # Pinecone
        store = get_vector_store(
            "pinecone",
            api_key="your-api-key",
            index_name="evidencing-agent",
            environment="us-west1-gcp",
            namespace="production"
        )
    """
    if store_type == "in_memory":
        from storage.vector_store.in_memory import InMemoryVectorStore
        return InMemoryVectorStore()

    elif store_type == "chroma":
        from storage.vector_store.chroma import ChromaVectorStore
        return ChromaVectorStore(**kwargs)

    elif store_type == "pinecone":
        from storage.vector_store.pinecone import PineconeVectorStore
        return PineconeVectorStore(**kwargs)

    else:
        raise ValueError(
            f"Unknown vector store type: {store_type}. "
            f"Supported types: in_memory, chroma, pinecone"
        )


def get_vector_store_from_config(config) -> VectorStore:
    """
    Create vector store from configuration object.

    Args:
        config: Configuration object with vector store settings

    Returns:
        VectorStore instance
    """
    store_type = config.vector_store_type

    if store_type == "in_memory":
        return get_vector_store("in_memory")

    elif store_type == "chroma":
        return get_vector_store(
            "chroma",
            collection_name=config.chroma_collection_name,
            persist_directory=config.chroma_persist_directory
        )

    elif store_type == "pinecone":
        return get_vector_store(
            "pinecone",
            api_key=config.pinecone_api_key,
            index_name=config.pinecone_index_name,
            environment=config.pinecone_environment,
            namespace=config.pinecone_namespace
        )

    else:
        raise ValueError(f"Unknown vector store type in config: {store_type}")
