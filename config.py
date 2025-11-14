"""Configuration for the evidencing agent."""
import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # LLM Configuration
    llm_provider: Literal["openai", "ollama"] = Field(
        default="ollama",
        description="LLM provider to use"
    )
    llm_model: str = Field(
        default="llama3.1:8b",
        description="Model name (e.g., 'gpt-4o' for OpenAI, 'llama3.1:8b' for Ollama)"
    )
    llm_temperature: float = Field(
        default=0.1,
        description="Temperature for LLM responses (lower = more deterministic)"
    )
    llm_base_url: str | None = Field(
        default="http://localhost:11434",
        description="Base URL for Ollama (ignored for OpenAI)"
    )
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key (required if provider=openai)"
    )

    # Embedding Configuration
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Embedding model for similarity search"
    )
    embedding_dimension: int = Field(
        default=384,
        description="Dimension of embeddings (384 for all-MiniLM-L6-v2)"
    )

    # Vector Store Configuration
    vector_store_type: Literal["in_memory", "chroma", "pinecone"] = Field(
        default="in_memory",
        description="Type of vector store to use"
    )

    # ChromaDB Configuration (when vector_store_type='chroma')
    chroma_collection_name: str = Field(
        default="evidencing_agent",
        description="ChromaDB collection name"
    )
    chroma_persist_directory: str | None = Field(
        default="data/chroma",
        description="ChromaDB persistence directory (None for in-memory)"
    )

    # Pinecone Configuration (when vector_store_type='pinecone')
    pinecone_api_key: str | None = Field(
        default=None,
        description="Pinecone API key"
    )
    pinecone_index_name: str = Field(
        default="evidencing-agent",
        description="Pinecone index name"
    )
    pinecone_environment: str | None = Field(
        default=None,
        description="Pinecone environment (e.g., 'us-west1-gcp')"
    )
    pinecone_namespace: str = Field(
        default="default",
        description="Pinecone namespace"
    )

    # Database Configuration
    database_path: Path = Field(
        default=Path("data/evidencing.db"),
        description="Path to SQLite database"
    )

    # RAG Configuration
    rag_chunk_size: int = Field(
        default=512,
        description="Size of commitment document chunks (in characters)"
    )
    rag_chunk_overlap: int = Field(
        default=50,
        description="Overlap between chunks (in characters)"
    )
    rag_top_k: int = Field(
        default=3,
        description="Number of RAG chunks to retrieve"
    )

    # Feedback Retrieval Configuration
    feedback_top_k: int = Field(
        default=5,
        description="Number of similar past decisions to retrieve"
    )
    similarity_threshold: float = Field(
        default=0.70,
        description="Minimum similarity score to consider feedback relevant"
    )

    # Confidence Thresholds
    confidence_high_threshold: float = Field(
        default=0.85,
        description="Threshold for high confidence"
    )
    confidence_medium_threshold: float = Field(
        default=0.70,
        description="Threshold for medium confidence"
    )
    confidence_low_threshold: float = Field(
        default=0.50,
        description="Threshold for low confidence (below = insufficient)"
    )

    # Frequency Weighting
    frequency_boost_factor: float = Field(
        default=0.15,
        description="Boost factor for each additional similar feedback (e.g., 0.15 = 15% boost)"
    )
    recency_weight: float = Field(
        default=0.1,
        description="Weight factor for recency (newer feedback gets slight boost)"
    )

    # Telemetry
    enable_telemetry: bool = Field(
        default=True,
        description="Enable detailed telemetry logging"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure database directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
