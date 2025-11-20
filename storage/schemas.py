"""Pydantic models for data validation and serialization."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================================
# Asset Models
# ============================================================================

class AssetURI(BaseModel):
    """Parsed asset URI."""

    raw_uri: str = Field(..., description="Full asset URI")
    asset_type: str = Field(..., description="Type from URI (e.g., 'database')")
    asset_descriptor: str = Field(..., description="Descriptor from URI (e.g., 'customer_data')")
    asset_domain: str = Field(..., description="Domain from URI (e.g., 'production')")

    @classmethod
    def from_uri(cls, uri: str) -> "AssetURI":
        """Parse asset URI in format: asset://type.descriptor.domain"""
        if not uri.startswith("asset://"):
            raise ValueError(f"Invalid asset URI format: {uri}. Expected 'asset://type.descriptor.domain'")

        path = uri.replace("asset://", "")
        parts = path.split(".")

        if len(parts) != 3:
            raise ValueError(
                f"Invalid asset URI format: {uri}. Expected exactly 3 parts: type.descriptor.domain"
            )

        return cls(
            raw_uri=uri,
            asset_type=parts[0],
            asset_descriptor=parts[1],
            asset_domain=parts[2]
        )


# ============================================================================
# Commitment Models
# ============================================================================

class Commitment(BaseModel):
    """Commitment document (e.g., SOC 2, GDPR)."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Commitment name (e.g., 'SOC 2 Type II - CC6.1')")
    description: str | None = Field(default=None, description="Brief description")
    doc_text: str = Field(..., description="Full document text")
    domain: str | None = Field(default=None, description="Domain (e.g., 'security', 'privacy')")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommitmentChunk(BaseModel):
    """Document chunk for RAG."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    commitment_id: str = Field(..., description="Parent commitment ID")
    chunk_text: str = Field(..., description="Chunk content")
    chunk_embedding: list[float] = Field(..., description="Embedding vector")
    chunk_index: int = Field(..., description="Order within commitment")


# ============================================================================
# Evidence and Decision Models
# ============================================================================

class CommitmentReference(BaseModel):
    """Reference to commitment documentation used in decision."""

    chunk_id: str
    text: str
    relevance: str | None = None
    note: str | None = None


class SimilarDecision(BaseModel):
    """Similar past decision that influenced current decision."""

    feedback_id: str
    asset_uri: str
    decision: str
    date: str
    similarity_score: float
    how_it_influenced: str


class Evidence(BaseModel):
    """Evidence supporting the decision."""

    commitment_analysis: str
    asset_characteristics: list[str]
    decision_rationale: str


class ConfidenceAssessment(BaseModel):
    """Confidence assessment for the decision."""

    level: Literal["high", "medium", "low", "insufficient"]
    score: float = Field(..., ge=0.0, le=1.0)

    factors: dict[str, Any] = Field(
        default_factory=dict,
        description="Factors contributing to confidence"
    )
    reasoning: str


class ScopingResponse(BaseModel):
    """Complete response from the agent."""

    decision: Literal["in-scope", "out-of-scope", "insufficient-data"]
    confidence_level: Literal["high", "medium", "low", "insufficient"]
    confidence_score: float = Field(..., ge=0.0, le=1.0)

    reasoning: str

    # For confident decisions
    evidence: Evidence | None = None
    commitment_references: list[CommitmentReference] = Field(default_factory=list)
    similar_decisions: list[SimilarDecision] = Field(default_factory=list)

    # For insufficient-data decisions
    missing_information: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    partial_analysis: str | None = None


# ============================================================================
# Scoping Decision Models
# ============================================================================

class RAGContext(BaseModel):
    """RAG context used in decision."""

    chunks_retrieved: int
    chunk_ids: list[str]
    avg_similarity: float
    top_similarity: float


class FeedbackContext(BaseModel):
    """Feedback context used in decision."""

    total_feedback_count: int
    retrieved_count: int
    avg_similarity: float
    frequency_clusters: int


class Telemetry(BaseModel):
    """Telemetry data for decision."""

    session_id: str
    timestamp: datetime

    query: dict[str, Any]
    rag_retrieval: dict[str, Any] | None = None
    feedback_retrieval: dict[str, Any] | None = None
    confidence_assessment: dict[str, Any] | None = None
    prompt_construction: dict[str, Any] | None = None
    llm_call: dict[str, Any] | None = None

    total_latency_ms: float
    errors: list[str] = Field(default_factory=list)


class ScopingDecision(BaseModel):
    """Complete scoping decision record."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Asset info
    asset_uri: str
    asset: AssetURI

    # Commitment
    commitment_id: str
    commitment_name: str

    # Query embedding
    query_embedding: list[float]

    # Decision
    decision: Literal["in-scope", "out-of-scope", "insufficient-data"]
    confidence_score: float
    confidence_level: Literal["high", "medium", "low", "insufficient"]

    # Response
    response: ScopingResponse

    # Context used
    rag_context: RAGContext | None = None
    feedback_context: FeedbackContext | None = None

    # Telemetry
    telemetry: Telemetry

    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Feedback Models
# ============================================================================

class DecisionFeedback(BaseModel):
    """Human feedback on a scoping decision."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    decision_id: str = Field(..., description="Original decision ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Original context
    asset_uri: str
    commitment_id: str
    query_embedding: list[float]

    # Original decision
    agent_decision: Literal["in-scope", "out-of-scope", "insufficient-data"]
    agent_reasoning: str

    # Human feedback
    rating: Literal["up", "down"]
    human_reason: str = Field(..., description="Why this was correct/incorrect")
    human_correction: str | None = Field(
        default=None,
        description="Correct decision and reasoning (for thumbs down)"
    )

    # Clustering metadata
    cluster_id: str | None = None
    frequency_weight: float = 1.0

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Agent State Models (for LangGraph)
# ============================================================================

class AgentState(BaseModel):
    """State passed through LangGraph nodes."""

    # Input
    asset_uri: str
    commitment_id: str | None = None  # Optional if using commitment_query
    commitment_query: str | None = None  # Natural language query for commitments
    commitment_name: str | None = None
    session_id: str = Field(default_factory=lambda: str(uuid4()))

    # Parsed asset
    asset: AssetURI | None = None

    # Commitment data
    commitment: Commitment | None = None  # Primary commitment (if using ID)
    related_commitments: list[Commitment] = Field(default_factory=list)  # Multiple commitments from search

    # RAG results
    rag_chunks: list[CommitmentChunk] = Field(default_factory=list)
    rag_context: RAGContext | None = None

    # Feedback results (list of dicts from feedback_processor.retrieve_similar_feedback)
    similar_feedback: list[dict[str, Any]] = Field(default_factory=list)
    feedback_context: FeedbackContext | None = None

    # Similar decisions (prior scoping decisions without feedback requirement)
    similar_decisions: list[dict[str, Any]] = Field(default_factory=list)

    # Tool results from MCP research tools
    tool_results: dict[str, Any] = Field(default_factory=dict)

    # Query embedding
    query_embedding: list[float] = Field(default_factory=list)

    # Confidence assessment
    confidence: ConfidenceAssessment | None = None

    # LLM response
    response: ScopingResponse | None = None

    # Final decision record
    decision: ScopingDecision | None = None

    # Telemetry tracking
    telemetry_data: dict[str, Any] = Field(default_factory=dict)
    start_time: float | None = None

    # Errors
    errors: list[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
