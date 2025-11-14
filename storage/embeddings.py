"""Embedding generation and similarity search."""
import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings


class EmbeddingService:
    """Service for generating embeddings and computing similarity."""

    def __init__(self):
        """Initialize embedding model."""
        self.model = SentenceTransformer(settings.embedding_model)
        self.dimension = settings.embedding_dimension

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def cosine_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def find_most_similar(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[list[float]],
        top_k: int = 5,
        threshold: float = 0.0
    ) -> list[tuple[int, float]]:
        """
        Find most similar embeddings to query.

        Returns:
            List of (index, similarity_score) tuples, sorted by similarity (highest first)
        """
        query_vec = np.array(query_embedding)
        candidate_vecs = np.array(candidate_embeddings)

        # Compute cosine similarity for all candidates
        similarities = []
        for idx, candidate_vec in enumerate(candidate_vecs):
            similarity = self.cosine_similarity(query_vec.tolist(), candidate_vec.tolist())
            if similarity >= threshold:
                similarities.append((idx, similarity))

        # Sort by similarity (highest first) and take top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]


# Global embedding service instance
embedding_service = EmbeddingService()
