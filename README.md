# 🔍 Evidencing Agent - Human-in-the-Loop Asset Scoping

A **LangGraph 1.0+** and **LangChain 1.0+** agent that makes evidence-based asset scoping decisions with human feedback integration. The agent determines if assets are in-scope or out-of-scope for compliance commitments (e.g., SOC 2, GDPR), learns from human corrections, and provides transparent, auditable decisions.

## 🎯 The Problem

Organizations must maintain compliance with various regulatory frameworks (SOC 2, GDPR, PCI DSS, HIPAA, etc.). A critical part of compliance is **scoping** - determining which assets (databases, APIs, systems) fall under which compliance commitments.

**Challenges:**
- **Manual scoping is time-consuming**: Security/compliance teams must review hundreds or thousands of assets
- **Decisions lack transparency**: It's unclear why an asset was deemed in-scope or out-of-scope
- **Knowledge is siloed**: Decisions aren't shared across the team, leading to inconsistencies
- **No learning from corrections**: When someone corrects a scoping decision, that knowledge is lost
- **Uncertainty is hidden**: Analysts make guesses instead of admitting they need more information

## 💡 The Solution

An AI agent that:

1. **Makes Evidence-Based Decisions**: Every decision includes citations from compliance docs and references to similar past decisions
2. **Learns from Human Feedback**: Thumbs up/down with corrections that improve future similar decisions
3. **Admits Uncertainty**: Says "I don't have enough data" instead of guessing, asking clarifying questions
4. **Never Blocks on Feedback**: Decisions are made immediately; feedback is collected async and used for future queries
5. **Provides Full Auditability**: Complete telemetry and checkpointing show exactly how each decision was made

## 🏆 Key Features

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

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│  User Input: Asset + Commitment                             │
│  Example: asset://database.customer_data.production         │
│           + "SOC 2 Type II - CC6.1"                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Parse Asset URI                                    │
│  Extract: type=database, descriptor=customer_data,          │
│           domain=production                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: RAG Retrieval (Commitment Documentation)          │
│  • Embed query: "Asset X + Commitment Y scoping"           │
│  • Find top-K similar chunks from commitment text           │
│  • Retrieved: Legal requirements, scoping criteria          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Feedback Retrieval (Past Decisions)               │
│  • Find similar past decisions via embedding search         │
│  • Apply frequency weighting (3 similar = higher weight)    │
│  • Apply recency boost (newer = higher weight)              │
│  • Retrieved: "Team doesn't use Heroku, use AWS" etc.      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Assess Confidence                                 │
│  Factors:                                                   │
│  • RAG chunk relevance (0-0.4)                             │
│  • Similar feedback quality & count (0-0.4)                │
│  • Feedback agreement/conflict (0-0.2)                     │
│  Score: 0.87 → "high" confidence                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴──────────────┐
        │                            │
        ▼                            ▼
┌──────────────────┐     ┌────────────────────────┐
│ Score < 0.5?     │     │ Score >= 0.5?          │
│ INSUFFICIENT     │     │ PROCEED                │
└──────┬───────────┘     └────────┬───────────────┘
       │                          │
       ▼                          ▼
┌──────────────────┐     ┌────────────────────────┐
│ Return:          │     │ STEP 5: Build Prompt   │
│ - Missing info   │     │ Include:               │
│ - Questions      │     │ • Commitment chunks    │
│ - Partial        │     │ • Past decisions       │
│   analysis       │     │ • Evidence tracking    │
└──────┬───────────┘     └────────┬───────────────┘
       │                          │
       │                          ▼
       │              ┌────────────────────────┐
       │              │ STEP 6: LLM Call       │
       │              │ Generate:              │
       │              │ • Decision + evidence  │
       │              │ • Commit references    │
       │              │ • Similar decisions    │
       │              └────────┬───────────────┘
       │                       │
       └───────────┬───────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 7: Save Decision                                      │
│  Store in DB: decision + evidence + telemetry + checkpoints │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Return to User                                             │
│  • Decision (in-scope / out-of-scope / insufficient-data)   │
│  • Evidence (expandable)                                    │
│  • References to commitment docs                            │
│  • Similar past decisions cited                             │
└─────────────────────────────────────────────────────────────┘
                      │
                      │ [ASYNC - Later, no blocking]
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Human Provides Feedback                                    │
│  👍 Correct: Reinforces this pattern                        │
│  👎 Incorrect: Reason + Correction                          │
│  Example: "Database doesn't contain PII" →                 │
│           "Should be out-of-scope"                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Store Feedback                                             │
│  • Compute embedding for future similarity search           │
│  • Link to original decision                                │
│  • Used in STEP 3 for next similar query                   │
└─────────────────────────────────────────────────────────────┘
```

### Decision Types

The agent produces three types of decisions:

1. **in-scope**: Asset falls under the compliance commitment
   - Example: Production database with customer PII → SOC 2 = IN-SCOPE
   - Includes full evidence and reasoning

2. **out-of-scope**: Asset doesn't fall under the commitment
   - Example: Test environment with fake data → SOC 2 = OUT-OF-SCOPE
   - Includes evidence for why it was excluded

3. **insufficient-data**: Not enough information to decide confidently
   - Example: Cache with unclear data types → INSUFFICIENT-DATA
   - Provides:
     - Missing information needed
     - Clarifying questions
     - Partial analysis of what was determined
   - **Key**: Never guesses when uncertain

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

**View checkpoint history (LangGraph 1.0+ feature):**
```bash
python -m cli.main checkpoint-history <thread-id>
```

**View current checkpoint state:**
```bash
python -m cli.main checkpoint-state <thread-id>
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

## 🧪 Testing & Walkthrough

### Initial Setup Verification

After installation, verify the system is ready:

```bash
# 1. Check sample data was loaded
python -m cli.main list-commitments

# Expected output: Shows SOC 2 CC6.1 and GDPR Article 5

# 2. Check LLM is configured
# For Ollama (local):
ollama list  # Should show llama3.1:8b or your configured model

# For OpenAI:
# Verify OPENAI_API_KEY is set in .env
```

### Complete Walkthrough: Testing the Feedback Loop

This walkthrough demonstrates the complete lifecycle: making decisions, providing feedback, and seeing the agent learn.

#### Step 1: Make Your First Decision

```bash
python -m cli.main decide "asset://database.customer_data.production" "SOC 2 Type II - CC6.1"
```

**Expected Output:**
- Decision: `in-scope` (high confidence)
- Reasoning based on commitment documentation
- No similar past decisions (this is the first!)
- Session ID displayed (save this for checkpoint viewing)

**Example:**
```
✅ IN-SCOPE
Confidence: high (0.85)

Reasoning:
This database stores customer data in production, which falls under SOC 2 CC6.1
requirements for data protection controls.

📊 Evidence:
  Commitment Analysis: SOC 2 CC6.1 explicitly covers systems storing customer data
  Asset Characteristics:
    • Production database (production domain)
    • Contains customer data (descriptor: customer_data)

Decision ID: abc-123-def
Session ID (Thread ID): xyz-456-session
💾 View checkpoints: cli checkpoint-history xyz-456-session
```

#### Step 2: View Decision Checkpoint History

```bash
python -m cli.main checkpoint-history xyz-456-session
```

**What You'll See:**
- All 7 checkpoints from the workflow
- State at each node (parse → RAG → feedback → confidence → prompt → LLM → save)
- Confidence evolution through the process

#### Step 3: Provide Feedback (Thumbs Up)

```bash
python -m cli.main feedback abc-123-def \
  --rating up \
  --reason "Correct - production database with customer PII should be in scope"
```

**Expected:**
```
👍 Feedback submitted successfully!
Feedback ID: feedback-789-xyz
```

#### Step 4: Make a Similar Decision (Agent Should Learn)

```bash
python -m cli.main decide "asset://database.user_profiles.production" "SOC 2 Type II - CC6.1"
```

**Expected Output:**
- Decision: `in-scope` (high confidence)
- **NEW**: References your previous feedback!
- Shows similar past decision with similarity score

**Example:**
```
✅ IN-SCOPE
Confidence: high (0.92)  ← Higher confidence due to past feedback!

🔍 Similar Past Decisions:
  • asset://database.customer_data.production → in-scope (similarity: 0.89)
    Feedback from 2024-11-14: "Correct - production database with customer PII should be in scope"
    How it influenced: Reinforces that production databases with customer data are in-scope
```

#### Step 5: Test Insufficient Data Scenario

```bash
python -m cli.main decide "asset://cache.session_store.temporary" "GDPR Article 5"
```

**Expected Output:**
- Decision: `insufficient-data`
- Lists missing information
- Asks clarifying questions
- Provides partial analysis

**Example:**
```
⚠️ INSUFFICIENT DATA TO DECIDE
Confidence: insufficient (0.35)

Missing Information:
  • What type of data does 'session_store' contain?
  • Is this cache storing any personal identifiable information?
  • What is the data retention period?

Clarifying Questions:
  • Does this cache store user identifiers or session data with PII?
  • How long is data retained in this cache?

Partial Analysis:
The asset appears to be a temporary cache. If it stores user identifiers or
personal data, it would be in-scope for GDPR.
```

#### Step 6: Provide Correcting Feedback

```bash
python -m cli.main feedback <decision-id> \
  --rating down \
  --reason "This cache only stores anonymous session IDs with no PII" \
  --correction "Should be OUT-OF-SCOPE - cache contains only anonymous identifiers with no way to link to real users"
```

#### Step 7: Test Similar Asset (Agent Learns from Correction)

```bash
python -m cli.main decide "asset://cache.user_sessions.temporary" "GDPR Article 5"
```

**Expected:**
- Agent now references your correction
- More confident decision based on your feedback

#### Step 8: View Statistics

```bash
python -m cli.main stats
```

**Shows:**
- Total feedback count
- Thumbs up/down ratio
- Accuracy percentage

#### Step 9: View All Decisions

```bash
python -m cli.main list-decisions --limit 10
```

**Shows:**
- Table of recent decisions
- Asset, commitment, decision, confidence
- Decision IDs for further investigation

### Testing with Streamlit UI

```bash
streamlit run ui/streamlit_app.py
```

**Walkthrough:**

1. **Make Decision** page:
   - Select asset and commitment
   - Click "🚀 Analyze"
   - View expandable evidence
   - Provide feedback inline

2. **View Decisions** page:
   - Browse past decisions
   - See decision details

3. **Checkpoints** page:
   - Enter a Session ID
   - View checkpoint history (7 checkpoints per decision)
   - Inspect state at each workflow step

4. **Manage Commitments** page:
   - View existing commitments
   - Add new commitments with legal text

5. **Statistics** page:
   - Overall feedback metrics
   - Per-commitment accuracy

### Testing Edge Cases

**Test 1: Conflicting Feedback**
```bash
# Same asset, different teams provide different feedback
# Most recent feedback wins
```

**Test 2: Frequency Weighting**
```bash
# Provide similar feedback 3 times
# Agent should heavily weight this pattern
```

**Test 3: No Feedback Available**
```bash
# New commitment with no past decisions
# Agent relies solely on RAG from commitment docs
```

### Verifying Checkpointing Works

```bash
# 1. Make a decision
python -m cli.main decide "asset://api.auth.production" "SOC 2 Type II - CC6.1"

# 2. Note the Session ID from output

# 3. View checkpoint history
python -m cli.main checkpoint-history <session-id>

# Should see 7 checkpoints:
# - parse_asset
# - retrieve_rag
# - retrieve_feedback
# - assess_confidence
# - build_prompt
# - llm_call
# - save_decision
```

### Expected Test Results

After running the complete walkthrough:

1. **Database populated**: 4-5 decisions stored
2. **Feedback loop working**: Agent cites past feedback
3. **Checkpoints visible**: Can inspect each workflow step
4. **Confidence assessment working**: Admits when data is insufficient
5. **Evidence tracking**: All decisions include citations and references

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

**Checkpointing** (ACTIVE):
- Every decision is saved at each step of the workflow
- View complete checkpoint history for any decision thread
- See state changes as the agent progresses through nodes
- Debug by inspecting state at any point in the process
- Uses MemorySaver (can upgrade to SqliteSaver for persistence)

**Advanced Features** (available for extension):
- **Interrupts**: Pause for human approval before continuing
- **Streaming**: Real-time updates as the graph executes
- **Persistent Checkpointing**: Upgrade to SqliteSaver or PostgresSaver

**LangChain 1.0+ Integration**:
- Structured outputs from LLMs (JSON mode)
- Better error handling and retries
- Improved streaming and async support

### 7. Using Checkpoints

Every decision creates a checkpoint at each workflow step. View checkpoints using:

**CLI**:
```bash
# View all checkpoints for a decision
python -m cli.main checkpoint-history <session-id>

# View current state
python -m cli.main checkpoint-state <session-id>
```

**Streamlit UI**:
- Navigate to "Checkpoints" page
- Enter a Session ID/Thread ID
- View checkpoint history and current state

**What Checkpoints Show**:
- State at each workflow node (parse, RAG, feedback, confidence, LLM, save)
- Asset and commitment information
- Confidence assessment at each step
- Telemetry data
- Next nodes to execute

**Use Cases**:
- Debug why a decision was made
- Understand how confidence changed through the workflow
- See what RAG chunks and feedback were retrieved
- Audit the decision-making process

## 🔮 Future Enhancements

- [x] LangGraph 1.0+ checkpointing with MemorySaver (DONE)
- [ ] Upgrade to SqliteSaver or PostgresSaver for persistent checkpoints
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
