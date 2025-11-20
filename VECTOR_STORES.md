# Vector Store Architecture

The evidencing agent now supports multiple vector database backends for scalable and flexible vector similarity search. This document explains the architecture, configuration, and usage of the vector store system.

## Architecture Overview

The system uses a **separation of concerns** approach:

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  (RAG Service, Feedback Processor, Agent Nodes)             │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         │                                 │
┌────────▼──────────┐           ┌─────────▼──────────┐
│   SQLite Database │           │   Vector Store      │
│   (Metadata)      │           │   (Embeddings)      │
├───────────────────┤           ├────────────────────┤
│ • Commitments     │           │ • Commitment chunks │
│ • Decisions       │           │ • Feedback vectors  │
│ • Feedback text   │           │ • Similarity search │
│ • Chunk text      │           │ • Metadata filters  │
└───────────────────┘           └────────────────────┘
```

### What Goes Where?

**SQLite Database:**
- Commitment metadata (name, description, legal text)
- Decision records (asset URI, decision, reasoning)
- Feedback metadata (rating, human reason, corrections)
- Chunk text and references

**Vector Store:**
- Commitment chunk embeddings
- Feedback query embeddings
- Fast similarity search
- Metadata filtering

## Supported Vector Stores

### 1. In-Memory (Default)

**Best for:**
- Local development
- Testing
- Small datasets (<10,000 vectors)
- No external dependencies

**Configuration:**
```bash
VECTOR_STORE_TYPE=in_memory
```

**Pros:**
- Zero setup
- Fast for small datasets
- No external services

**Cons:**
- Data lost on restart
- Not suitable for production
- Limited scalability

---

### 2. ChromaDB

**Best for:**
- Local development with persistence
- Self-hosted deployments
- Medium datasets (10,000 - 1M vectors)
- Easy setup

**Installation:**
```bash
pip install chromadb>=0.4.0
```

**Configuration:**
```bash
VECTOR_STORE_TYPE=chroma
CHROMA_COLLECTION_NAME=evidencing_agent
CHROMA_PERSIST_DIRECTORY=data/chroma  # Or empty for in-memory
```

**Pros:**
- Easy local setup
- Persistent storage
- Good performance
- Self-hosted (no cloud costs)

**Cons:**
- Requires additional dependency
- Limited horizontal scaling

---

### 3. Pinecone

**Best for:**
- Production deployments
- Large datasets (>1M vectors)
- Managed service (no infrastructure)
- High performance at scale

**Installation:**
```bash
pip install pinecone-client>=3.0.0
```

**Setup:**
1. Create account at [pinecone.io](https://www.pinecone.io)
2. Create index with:
   - Dimension: 384 (for all-MiniLM-L6-v2)
   - Metric: cosine
   - Spec: Serverless (recommended)

**Configuration:**
```bash
VECTOR_STORE_TYPE=pinecone
PINECONE_API_KEY=your-api-key-here
PINECONE_INDEX_NAME=evidencing-agent
PINECONE_ENVIRONMENT=us-west1-gcp  # Your environment
PINECONE_NAMESPACE=default
```

**Pros:**
- Fully managed
- Scales to billions of vectors
- High performance
- Built-in monitoring

**Cons:**
- Requires API key
- Cloud-based (internet required)
- Costs at scale

## Configuration

### Environment Variables

Edit `.env` file:

```bash
# Vector Store Configuration
VECTOR_STORE_TYPE=in_memory  # Options: in_memory, chroma, pinecone

# ChromaDB (if using)
CHROMA_COLLECTION_NAME=evidencing_agent
CHROMA_PERSIST_DIRECTORY=data/chroma

# Pinecone (if using)
PINECONE_API_KEY=your-api-key
PINECONE_INDEX_NAME=evidencing-agent
PINECONE_ENVIRONMENT=us-west1-gcp
PINECONE_NAMESPACE=default
```

### Programmatic Configuration

```python
from storage.vector_store.factory import get_vector_store

# In-memory
store = get_vector_store("in_memory")

# ChromaDB
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
```

## Usage Examples

### Basic Operations

```python
from storage.vector_store.base import VectorDocument
from storage.vector_store.factory import get_vector_store

# Get vector store
store = get_vector_store("chroma", persist_directory="./data/chroma")

# Add documents
documents = [
    VectorDocument(
        id="chunk-1",
        text="SOC 2 requires access controls",
        embedding=[0.1, 0.2, ...],  # 384-dim vector
        metadata={"type": "commitment_chunk", "commitment_id": "soc2"}
    )
]
store.add_documents(documents)

# Search
results = store.search(
    query_embedding=[0.15, 0.18, ...],
    top_k=5,
    filter_metadata={"type": "commitment_chunk"},
    score_threshold=0.7
)

for result in results:
    print(f"{result.id}: {result.score} - {result.text}")

# Delete
store.delete_by_id("chunk-1")
store.delete_by_metadata({"commitment_id": "soc2"})
```

### Integration with RAG

The RAG service automatically uses the configured vector store:

```python
from storage.rag import rag_service
from storage.schemas import Commitment

# Process commitment (stores vectors in vector store)
commitment = Commitment(
    name="SOC 2 CC6.1",
    doc_text="Access control requirements..."
)

chunks = rag_service.process_and_store_commitment(commitment)

# Search uses vector store automatically
context = rag_service.get_commitment_context(
    query_embedding=query_vector,
    commitment_id=commitment.id
)
```

### Integration with Feedback

Feedback processor uses vector store for similarity search:

```python
from feedback.processor import feedback_processor

# Retrieve similar feedback (uses vector store)
similar = feedback_processor.retrieve_similar_feedback(
    query_embedding=query_vector,
    commitment_id="soc2",
    top_k=5,
    threshold=0.7
)

for fb in similar:
    print(f"Similarity: {fb['similarity']}, Rating: {fb['rating']}")
```

## Migration Guide

### Switching Vector Stores

When switching vector stores, embeddings need to be re-indexed:

1. **Change configuration** in `.env`:
   ```bash
   VECTOR_STORE_TYPE=chroma  # Changed from in_memory
   ```

2. **Re-index commitments**:
   ```python
   from storage import db
   from storage.rag import rag_service

   # Get all commitments
   commitments = db.list_commitments()

   # Re-process each commitment
   for commitment in commitments:
       rag_service.process_and_store_commitment(commitment)
       print(f"Re-indexed: {commitment.name}")
   ```

3. **Re-index feedback** (if applicable):
   ```python
   from feedback.collector import feedback_collector
   from storage import db

   # Get all feedback
   all_feedback = db.list_feedback(limit=10000)

   # Re-submit to vector store
   # Note: This requires access to original decision data
   # See feedback/collector.py for implementation
   ```

### Data Backup

**SQLite** (always backed up):
```bash
cp data/evidencing.db data/evidencing.db.backup
```

**ChromaDB**:
```bash
cp -r data/chroma data/chroma.backup
```

**Pinecone**:
- Data is managed by Pinecone
- Use Pinecone's backup features
- Export to another index if needed

## Performance Considerations

### In-Memory
- **Search time**: O(n) linear scan
- **Memory**: All vectors in RAM
- **Recommended**: <10,000 vectors

### ChromaDB
- **Search time**: O(log n) with HNSW index
- **Disk I/O**: May impact performance
- **Recommended**: 10,000 - 1M vectors

### Pinecone
- **Search time**: O(log n), optimized
- **Network latency**: ~50-100ms per query
- **Recommended**: >100,000 vectors, production workloads

## Troubleshooting

### ChromaDB: "Collection already exists"
```python
# Clear and recreate
from storage.vector_store import get_vector_store
store = get_vector_store("chroma", persist_directory="./data/chroma")
store.clear()
```

### Pinecone: "Index not found"
Create index first:
```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="your-key")
pc.create_index(
    name="evidencing-agent",
    dimension=384,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1")
)
```

### Vectors not found after restart
- **In-memory**: Expected behavior (no persistence)
- **ChromaDB**: Check `CHROMA_PERSIST_DIRECTORY` is set
- **Pinecone**: Check namespace matches

## Best Practices

1. **Start with in-memory** for development
2. **Use ChromaDB** for self-hosted production
3. **Use Pinecone** for large-scale deployments
4. **Always backup SQLite** database (has metadata)
5. **Monitor vector store size** and performance
6. **Use metadata filters** to improve search quality
7. **Re-index periodically** if embeddings model changes

## API Reference

See:
- `storage/vector_store/base.py` - Abstract interface
- `storage/vector_store/in_memory.py` - In-memory implementation
- `storage/vector_store/chroma.py` - ChromaDB implementation
- `storage/vector_store/pinecone.py` - Pinecone implementation
- `storage/vector_store/factory.py` - Factory for creating stores
