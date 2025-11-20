"""Storage module for database, embeddings, and RAG."""
from storage.commitment_search import CommitmentSearchService, commitment_search_service
from storage.database import Database, db
from storage.embeddings import EmbeddingService, embedding_service
from storage.rag import RAGService, rag_service
from storage.schemas import (
    AgentState,
    AssetURI,
    Commitment,
    CommitmentChunk,
    CommitmentReference,
    ConfidenceAssessment,
    DecisionFeedback,
    Evidence,
    FeedbackContext,
    RAGContext,
    ScopingDecision,
    ScopingResponse,
    SimilarDecision,
    Telemetry,
)
from storage.vector_store import VectorDocument, VectorStore, vector_store

__all__ = [
    # Database
    "Database",
    "db",
    # Embeddings
    "EmbeddingService",
    "embedding_service",
    # RAG
    "RAGService",
    "rag_service",
    # Commitment Search
    "CommitmentSearchService",
    "commitment_search_service",
    # Vector Store
    "VectorStore",
    "vector_store",
    "VectorDocument",
    # Schemas
    "AgentState",
    "AssetURI",
    "Commitment",
    "CommitmentChunk",
    "CommitmentReference",
    "ConfidenceAssessment",
    "DecisionFeedback",
    "Evidence",
    "FeedbackContext",
    "RAGContext",
    "ScopingDecision",
    "ScopingResponse",
    "SimilarDecision",
    "Telemetry",
]
