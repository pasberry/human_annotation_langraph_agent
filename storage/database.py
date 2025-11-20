"""Database operations for SQLite."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from config import settings
from storage.schemas import (
    Commitment,
    CommitmentChunk,
    DecisionFeedback,
    ScopingDecision,
)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Path | None = None):
        """Initialize database connection."""
        self.db_path = db_path or settings.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection with context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Commitments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commitments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    doc_text TEXT NOT NULL,
                    domain TEXT,
                    created_at DATETIME NOT NULL
                )
            """)

            # Commitment chunks for RAG
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commitment_chunks (
                    id TEXT PRIMARY KEY,
                    commitment_id TEXT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    chunk_embedding TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    FOREIGN KEY (commitment_id) REFERENCES commitments(id)
                )
            """)

            # Scoping decisions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scoping_decisions (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME NOT NULL,

                    asset_uri TEXT NOT NULL,
                    asset_type TEXT,
                    asset_descriptor TEXT,
                    asset_domain TEXT,

                    commitment_id TEXT NOT NULL,
                    commitment_name TEXT NOT NULL,

                    query_embedding TEXT NOT NULL,

                    decision TEXT NOT NULL CHECK (decision IN ('in-scope', 'out-of-scope', 'insufficient-data')),
                    confidence_score REAL NOT NULL,
                    confidence_level TEXT NOT NULL,

                    response TEXT NOT NULL,

                    rag_context TEXT,
                    feedback_context TEXT,

                    telemetry TEXT NOT NULL,

                    session_id TEXT NOT NULL,
                    created_at DATETIME NOT NULL,

                    FOREIGN KEY (commitment_id) REFERENCES commitments(id)
                )
            """)

            # Decision feedback
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decision_feedback (
                    id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,

                    asset_uri TEXT NOT NULL,
                    commitment_id TEXT NOT NULL,
                    query_embedding TEXT NOT NULL,

                    agent_decision TEXT NOT NULL,
                    agent_reasoning TEXT NOT NULL,

                    rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
                    human_reason TEXT NOT NULL,
                    human_correction TEXT,

                    cluster_id TEXT,
                    frequency_weight REAL DEFAULT 1.0,

                    created_at DATETIME NOT NULL,

                    FOREIGN KEY (decision_id) REFERENCES scoping_decisions(id),
                    FOREIGN KEY (commitment_id) REFERENCES commitments(id)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scoping_asset
                ON scoping_decisions(asset_uri)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scoping_commitment
                ON scoping_decisions(commitment_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scoping_decision
                ON scoping_decisions(decision)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scoping_timestamp
                ON scoping_decisions(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_commitment
                ON decision_feedback(commitment_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_rating
                ON decision_feedback(rating)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
                ON decision_feedback(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_commitment
                ON commitment_chunks(commitment_id)
            """)

    # ========================================================================
    # Commitment Operations
    # ========================================================================

    def add_commitment(self, commitment: Commitment) -> None:
        """Add a new commitment to the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO commitments (id, name, description, doc_text, domain, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                commitment.id,
                commitment.name,
                commitment.description,
                commitment.doc_text,
                commitment.domain,
                commitment.created_at.isoformat()
            ))

    def get_commitment(self, commitment_id: str) -> Commitment | None:
        """Get commitment by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM commitments WHERE id = ?", (commitment_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return Commitment(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                doc_text=row["doc_text"],
                domain=row["domain"],
                created_at=datetime.fromisoformat(row["created_at"])
            )

    def get_commitment_by_name(self, name: str) -> Commitment | None:
        """Get commitment by name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM commitments WHERE name = ?", (name,))
            row = cursor.fetchone()

            if not row:
                return None

            return Commitment(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                doc_text=row["doc_text"],
                domain=row["domain"],
                created_at=datetime.fromisoformat(row["created_at"])
            )

    def list_commitments(self) -> list[Commitment]:
        """List all commitments."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM commitments ORDER BY name")
            rows = cursor.fetchall()

            return [
                Commitment(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    doc_text=row["doc_text"],
                    domain=row["domain"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
                for row in rows
            ]

    # ========================================================================
    # Commitment Chunk Operations (RAG)
    # ========================================================================

    def add_commitment_chunks(self, chunks: list[CommitmentChunk]) -> None:
        """Add commitment chunks for RAG."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for chunk in chunks:
                cursor.execute("""
                    INSERT INTO commitment_chunks (id, commitment_id, chunk_text, chunk_embedding, chunk_index)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    chunk.id,
                    chunk.commitment_id,
                    chunk.chunk_text,
                    json.dumps(chunk.chunk_embedding),
                    chunk.chunk_index
                ))

    def get_commitment_chunks(self, commitment_id: str) -> list[CommitmentChunk]:
        """Get all chunks for a commitment."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM commitment_chunks
                WHERE commitment_id = ?
                ORDER BY chunk_index
            """, (commitment_id,))
            rows = cursor.fetchall()

            return [
                CommitmentChunk(
                    id=row["id"],
                    commitment_id=row["commitment_id"],
                    chunk_text=row["chunk_text"],
                    chunk_embedding=json.loads(row["chunk_embedding"]),
                    chunk_index=row["chunk_index"]
                )
                for row in rows
            ]

    def get_all_chunks(self) -> list[CommitmentChunk]:
        """Get all commitment chunks (for similarity search)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM commitment_chunks ORDER BY commitment_id, chunk_index")
            rows = cursor.fetchall()

            return [
                CommitmentChunk(
                    id=row["id"],
                    commitment_id=row["commitment_id"],
                    chunk_text=row["chunk_text"],
                    chunk_embedding=json.loads(row["chunk_embedding"]),
                    chunk_index=row["chunk_index"]
                )
                for row in rows
            ]

    # ========================================================================
    # Scoping Decision Operations
    # ========================================================================

    def add_scoping_decision(self, decision: ScopingDecision) -> None:
        """Add a scoping decision."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scoping_decisions (
                    id, timestamp, asset_uri, asset_type, asset_descriptor, asset_domain,
                    commitment_id, commitment_name, query_embedding, decision,
                    confidence_score, confidence_level, response, rag_context,
                    feedback_context, telemetry, session_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.id,
                decision.timestamp.isoformat(),
                decision.asset_uri,
                decision.asset.asset_type,
                decision.asset.asset_descriptor,
                decision.asset.asset_domain,
                decision.commitment_id,
                decision.commitment_name,
                json.dumps(decision.query_embedding),
                decision.decision,
                decision.confidence_score,
                decision.confidence_level,
                decision.response.model_dump_json(),
                json.dumps(decision.rag_context.model_dump()) if decision.rag_context else None,
                json.dumps(decision.feedback_context.model_dump()) if decision.feedback_context else None,
                decision.telemetry.model_dump_json(),
                decision.session_id,
                decision.created_at.isoformat()
            ))

    def get_scoping_decision(self, decision_id: str) -> dict | None:
        """Get a scoping decision by ID (returns raw dict)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scoping_decisions WHERE id = ?", (decision_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return dict(row)

    def list_scoping_decisions(
        self,
        commitment_id: str | None = None,
        asset_uri: str | None = None,
        limit: int = 100
    ) -> list[dict]:
        """List scoping decisions with optional filters."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM scoping_decisions WHERE 1=1"
            params = []

            if commitment_id:
                query += " AND commitment_id = ?"
                params.append(commitment_id)

            if asset_uri:
                query += " AND asset_uri = ?"
                params.append(asset_uri)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    # ========================================================================
    # Feedback Operations
    # ========================================================================

    def add_feedback(self, feedback: DecisionFeedback) -> None:
        """Add decision feedback."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO decision_feedback (
                    id, decision_id, timestamp, asset_uri, commitment_id,
                    query_embedding, agent_decision, agent_reasoning,
                    rating, human_reason, human_correction, cluster_id,
                    frequency_weight, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback.id,
                feedback.decision_id,
                feedback.timestamp.isoformat(),
                feedback.asset_uri,
                feedback.commitment_id,
                json.dumps(feedback.query_embedding),
                feedback.agent_decision,
                feedback.agent_reasoning,
                feedback.rating,
                feedback.human_reason,
                feedback.human_correction,
                feedback.cluster_id,
                feedback.frequency_weight,
                feedback.created_at.isoformat()
            ))

    def get_all_feedback(self) -> list[DecisionFeedback]:
        """Get all feedback entries (for similarity search)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM decision_feedback ORDER BY timestamp DESC")
            rows = cursor.fetchall()

            return [
                DecisionFeedback(
                    id=row["id"],
                    decision_id=row["decision_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    asset_uri=row["asset_uri"],
                    commitment_id=row["commitment_id"],
                    query_embedding=json.loads(row["query_embedding"]),
                    agent_decision=row["agent_decision"],
                    agent_reasoning=row["agent_reasoning"],
                    rating=row["rating"],
                    human_reason=row["human_reason"],
                    human_correction=row["human_correction"],
                    cluster_id=row["cluster_id"],
                    frequency_weight=row["frequency_weight"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
                for row in rows
            ]

    def list_feedback(
        self,
        decision_id: str | None = None,
        commitment_id: str | None = None,
        rating: str | None = None,
        limit: int = 100
    ) -> list[DecisionFeedback]:
        """List feedback with optional filters."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM decision_feedback WHERE 1=1"
            params = []

            if decision_id:
                query += " AND decision_id = ?"
                params.append(decision_id)

            if commitment_id:
                query += " AND commitment_id = ?"
                params.append(commitment_id)

            if rating:
                query += " AND rating = ?"
                params.append(rating)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [
                DecisionFeedback(
                    id=row["id"],
                    decision_id=row["decision_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    asset_uri=row["asset_uri"],
                    commitment_id=row["commitment_id"],
                    query_embedding=json.loads(row["query_embedding"]),
                    agent_decision=row["agent_decision"],
                    agent_reasoning=row["agent_reasoning"],
                    rating=row["rating"],
                    human_reason=row["human_reason"],
                    human_correction=row["human_correction"],
                    cluster_id=row["cluster_id"],
                    frequency_weight=row["frequency_weight"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
                for row in rows
            ]


# Global database instance
db = Database()
