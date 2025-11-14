# 🔍 Evidencing Agent - Human-in-the-Loop Asset Scoping

A **LangGraph 1.0+** and **LangChain 1.0+** agent that makes evidence-based asset scoping decisions with human feedback integration. The agent determines if assets are in-scope or out-of-scope for compliance commitments (e.g., SOC 2, GDPR), learns from human corrections, and provides transparent, auditable decisions.

## 🎯 Key Features

- **LangGraph 1.0+ Architecture**: Type-safe state management with Pydantic models
- **Evidence-Based Decisions**: Every decision includes citations, references, and reasoning
- **Human-in-the-Loop Feedback**: Thumbs up/down feedback with corrections that improve future decisions
- **RAG-Powered**: Retrieves relevant commitment documentation to inform decisions
- **Confidence Assessment**: Declares when it doesn't have enough information to decide
- **Non-Blocking**: Never waits for feedback - all feedback is async
- **Frequency-Weighted Learning**: Similar feedback patterns are weighted higher
- **Complete Telemetry**: Every decision is fully auditable with detailed telemetry
- **Dual Interface**: CLI and Streamlit UI

## 🏗️ Architecture

```
User Query (Asset + Commitment)
    ↓
[Parse Asset URI] → asset://type.descriptor.domain
    ↓
[RAG Retrieval] → Get relevant commitment documentation chunks
    ↓
[Feedback Retrieval] → Find similar past decisions (frequency-weighted)
    ↓
[Assess Confidence] → Determine if we have enough data
    ↓
[Build Prompt] → Construct evidence-rich prompt
    ↓
[LLM Call] → Generate structured decision with evidence
    ↓
[Save Decision] → Store in database with full telemetry
    ↓
Return to User (with expandable evidence)

[ASYNC - Later]
    ↓
Human provides feedback (👍/👎 + reason + correction)
    ↓
Store feedback → Used in future similar queries
```

## 📦 Installation

### Prerequisites

- Python 3.10+
- LangGraph 1.0+ and LangChain 1.0+ (installed via requirements.txt)
- Ollama (for local LLM) or OpenAI API key

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd human_annotation_langraph_agent
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

For Ollama (local):
```bash
# .env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
LLM_BASE_URL=http://localhost:11434
```

For OpenAI:
```bash
# .env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=your-api-key-here
```

5. **Load sample data**
```bash
python setup_sample_data.py
```

This will create:
- SOC 2 Type II - CC6.1 commitment
- GDPR Article 5 commitment

## 🚀 Usage

### CLI Interface

**Make a scoping decision:**
```bash
python -m cli.main decide "asset://database.customer_data.production" "SOC 2 Type II - CC6.1"
```

**Submit feedback:**
```bash
python -m cli.main feedback <decision-id> --rating down --reason "Database doesn't contain PII" --correction "Should be out-of-scope"
```

**List commitments:**
```bash
python -m cli.main list-commitments
```

**View past decisions:**
```bash
python -m cli.main list-decisions --limit 10
```

**Add a new commitment:**
```bash
python -m cli.main add-commitment "PCI DSS 3.2.1" path/to/pci_dss.txt --domain security
```

**View statistics:**
```bash
python -m cli.main stats
```

### Streamlit UI

```bash
streamlit run ui/streamlit_app.py
```

The UI provides:
- Interactive decision-making interface
- Visual feedback forms
- Decision history browser
- Commitment management
- Statistics dashboard

## 📊 Decision Flow Example

### Example 1: Confident Decision

**Input:**
- Asset: `asset://database.customer_data.production`
- Commitment: `SOC 2 Type II - CC6.1`

**Output:**
```
✅ IN-SCOPE
Confidence: high (0.92)

Reasoning:
This database stores customer PII and is used in production, which falls
under SOC 2 CC6.1 requirements for data protection controls.

Evidence:
✓ Commitment Analysis: SOC 2 CC6.1 explicitly covers systems storing
  sensitive customer data
✓ Asset Characteristics:
  • Production database (production domain)
  • Contains customer data (descriptor: customer_data)
✓ Similar Past Decision: asset://database.user_profiles.production →
  in-scope (similarity: 0.89)

Decision ID: abc-123-def
```

### Example 2: Insufficient Data

**Input:**
- Asset: `asset://cache.session_store.temporary`
- Commitment: `GDPR Article 5`

**Output:**
```
⚠️ INSUFFICIENT DATA TO DECIDE
Confidence: insufficient (0.35)

Reasoning:
Cannot make a definitive scoping decision due to lack of context about
the asset and limited historical decisions for this commitment.

Missing Information:
• What type of data does 'session_store' contain?
• Is this cache storing any personal identifiable information?
• What is the data retention period?

Clarifying Questions:
• Does this cache store user identifiers or session data with PII?
• How long is data retained in this cache?
• Is this cache accessible to external systems?

Partial Analysis:
The asset appears to be a temporary cache, which might contain session
data. If it stores user identifiers or personal data, it would be in-scope
for GDPR.
```

**Human provides feedback:**
- Reason: "This cache stores only anonymous session IDs with no PII"
- Correction: "Should be OUT-OF-SCOPE"

**Next similar query:** The agent will use this feedback to decide!

## 🗄️ Database Schema

The system uses SQLite with the following tables:

- **commitments**: Compliance commitments (SOC 2, GDPR, etc.)
- **commitment_chunks**: RAG chunks of commitment documentation
- **scoping_decisions**: All scoping decisions with evidence and telemetry
- **decision_feedback**: Human feedback on decisions

All tables store JSON blobs for complex data, queryable via SQLite JSON functions.

## 🔧 Configuration

See `config.py` for all configurable parameters:

- **LLM Settings**: Provider, model, temperature
- **Embedding Settings**: Model, dimensions
- **RAG Settings**: Chunk size, overlap, top-k retrieval
- **Feedback Settings**: Similarity threshold, top-k
- **Confidence Thresholds**: High, medium, low, insufficient

## 🧪 Testing

**Test the agent:**
```bash
# Make a decision
python -m cli.main decide "asset://database.analytics.production" "SOC 2 Type II - CC6.1"

# Provide feedback
python -m cli.main feedback <decision-id> --rating up --reason "Correct - analytics DB has customer data"

# Make similar decision (should use feedback)
python -m cli.main decide "asset://database.metrics.production" "SOC 2 Type II - CC6.1"
```

## 📁 Project Structure

```
human_annotation_langraph_agent/
├── agent/
│   ├── nodes/              # LangGraph nodes
│   │   ├── parse_asset.py
│   │   ├── retrieve_rag.py
│   │   ├── retrieve_feedback.py
│   │   ├── assess_confidence.py
│   │   ├── build_prompt.py
│   │   ├── llm_call.py
│   │   └── save_decision.py
│   └── graph.py            # LangGraph workflow
├── storage/
│   ├── database.py         # SQLite operations
│   ├── embeddings.py       # Embedding service
│   ├── rag.py              # RAG service
│   └── schemas.py          # Pydantic models
├── feedback/
│   ├── collector.py        # Feedback collection
│   └── processor.py        # Feedback analysis
├── cli/
│   └── main.py             # CLI interface
├── ui/
│   └── streamlit_app.py    # Streamlit UI
├── sample_data/            # Sample commitments
├── config.py               # Configuration
├── setup_sample_data.py    # Sample data loader
└── requirements.txt
```

## 🎓 How It Works

### 1. Asset URI Format
Assets are identified by URIs: `asset://type.descriptor.domain`

Examples:
- `asset://database.customer_data.production`
- `asset://api.authentication.staging`
- `asset://storage.backups.archive`

### 2. RAG Retrieval
Commitment documents are chunked and embedded. When a query comes in:
1. Generate query embedding
2. Find top-K similar chunks via cosine similarity
3. Include in prompt with chunk IDs for citation

### 3. Feedback Learning
When humans provide feedback:
1. Store with embedding of original query
2. On next query, find similar past feedback
3. Apply frequency weighting (more similar feedback = higher weight)
4. Include in prompt as few-shot examples
5. LLM cites how it influenced the decision

### 4. Confidence Assessment
Confidence is calculated based on:
- RAG chunk relevance (0-0.4)
- Similar feedback count and quality (0-0.4)
- Feedback agreement/conflict (0-0.2)

Thresholds:
- High: ≥ 0.85
- Medium: 0.70-0.84
- Low: 0.50-0.69
- Insufficient: < 0.50

### 5. Evidence Tracking
Every decision includes:
- Commitment references (with chunk IDs)
- Similar past decisions (with IDs and similarity scores)
- Asset characteristics
- Decision rationale
- What was considered and rejected

### 6. LangGraph 1.0+ Features
This project leverages LangGraph 1.0+ and LangChain 1.0+ capabilities:

**Type Safety with Pydantic**:
- State is defined using Pydantic models (`AgentState`)
- Automatic validation and serialization
- Better IDE support and error catching

**State Management**:
- Nodes can return full state or partial dict updates
- Automatic state merging and validation
- Immutable state updates for predictability

**Advanced Features** (available for extension):
- **Checkpointing**: Save and resume workflow state
- **Interrupts**: Pause for human approval before continuing
- **Streaming**: Real-time updates as the graph executes
- **Persistence**: Store conversation history across sessions

**LangChain 1.0+ Integration**:
- Structured outputs from LLMs (JSON mode)
- Better error handling and retries
- Improved streaming and async support

## 🔮 Future Enhancements

- [ ] LangGraph 1.0+ checkpointing for state persistence across sessions
- [ ] Interrupt points for human approval before final decisions
- [ ] Streaming responses for real-time UI updates
- [ ] Multi-user conflict resolution
- [ ] Feedback approval workflow
- [ ] Advanced clustering algorithms
- [ ] Decision audit trail visualization
- [ ] Bulk asset import/analysis
- [ ] Integration with asset management systems
- [ ] Custom confidence threshold tuning per commitment
- [ ] Decision templates for common patterns

## 📄 License

MIT License

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

## 📧 Support

For questions or issues, please open a GitHub issue.
