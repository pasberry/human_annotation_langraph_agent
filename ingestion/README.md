# Commitment Ingestion Pipeline

This package provides the **external ingestion process** for commitment documents. It runs **separately** from the agent to prepare commitments for use.

## What It Does

The ingestion service:

1. **Reads** markdown files containing commitment documents
2. **Uses LLM** to generate rich semantic descriptions
3. **Chunks** documents for RAG (Retrieval-Augmented Generation)
4. **Embeds** text chunks as vectors
5. **Stores** everything:
   - Full document → SQLite
   - Document chunks → SQLite + Vector DB
   - Searchable summary → Vector DB

## Why Separate from Agent?

The agent should **consume** commitments, not ingest them. This separation:

- ✅ Keeps agent focused on decision-making
- ✅ Allows batch processing of commitments
- ✅ Enables different ingestion strategies (watch folders, API uploads, etc.)
- ✅ Supports LLM-generated descriptions (too slow for real-time)

## Usage

### Single File

```bash
# Ingest one commitment file
python -m ingestion.commitment_ingestion demo/commitments/customer_data_usage_policy.md \
    --name "Customer Data Usage Policy"
```

### Batch Directory

```bash
# Ingest all markdown files in a directory
python -m ingestion.commitment_ingestion demo/commitments/
```

### Force Regenerate Descriptions

```bash
# Regenerate LLM descriptions for existing commitments
python -m ingestion.commitment_ingestion demo/commitments/ --force
```

### Custom Pattern

```bash
# Only process files matching pattern
python -m ingestion.commitment_ingestion policies/ --pattern "gdpr*.md"
```

## LLM-Generated Descriptions

The key innovation is **using LLM to generate semantic descriptions** instead of static "domain" labels.

### Old Way (Static Domain):
```python
Commitment(
    name="Minor Data Protection",
    description="Privacy policy",  # Too vague!
    domain="privacy"  # Too simple!
)
```

### New Way (LLM-Generated):
```python
Commitment(
    name="Minor Data Protection",
    description="Prohibits using data from users under 18 for advertising, marketing, behavioral profiling, recommendation engines, A/B testing, cross-platform tracking, and machine learning training. Only permits age verification, parental consent, fraud prevention, and core service delivery."  # Rich semantic content!
)
```

The LLM description captures:
- **Data types** governed (minor data, user age, etc.)
- **Prohibited purposes** (advertising, ML training, profiling)
- **Permitted purposes** (verification, safety, service delivery)
- **Keywords** for semantic search

This makes vector search **much more effective** because the description itself contains the concepts users will search for.

## How It Works

### Step 1: LLM Analyzes Document

```
Prompt: "Analyze this policy and extract key prohibitions and permissions..."

LLM Output: "Prohibits customer phone numbers for marketing calls, SMS campaigns,
robocalls, and telemarketing. Only permits transactional order confirmations,
customer-initiated support, and security alerts. Enforces TCPA compliance."
```

### Step 2: Store Summary in Vector DB

The LLM description gets embedded and stored with metadata `type="commitment_summary"`.

### Step 3: Users Query Naturally

```python
# User asks: "no telemarketing"
agent.run(
    asset_uri="database.customer_phone.sms_campaigns",
    commitment_query="no telemarketing"
)

# Vector search finds: "Telemarketing Restrictions" commitment
# Because LLM description contains "telemarketing", "SMS campaigns", etc.
```

## Example Output

When you run ingestion, you'll see:

```
📄 Ingesting: Customer Data Usage Policy
   File: demo/commitments/customer_data_usage_policy.md
   ✓ Loaded 12453 characters
   🤖 Generating semantic description with LLM...
   ✓ Description: Prohibits customer personal data for marketing, product analytics, business intelligence, third-party sharing, and employee monitoring without explicit consent. Only permits order fulfillment, customer support, fraud prevention, and legal compliance...
   ✓ Stored in database (ID: abc123)
   📦 Chunking document...
   ✓ Created 23 chunks for RAG
   🔍 Making commitment searchable...
   ✓ Commitment summary stored in vector DB
   ✅ Ingestion complete!
```

## API Usage

You can also use the service programmatically:

```python
from ingestion import commitment_ingestion_service
from pathlib import Path

# Single file
commitment = commitment_ingestion_service.ingest_commitment(
    name="GDPR Article 5",
    file_path=Path("policies/gdpr_article5.md")
)

# Batch directory
commitments = commitment_ingestion_service.ingest_directory(
    directory=Path("policies/"),
    pattern="*.md"
)
```

## Production Deployment

For production, you might want:

### Option 1: Cron Job
```bash
# Run ingestion nightly for new/updated policies
0 2 * * * cd /app && python -m ingestion.commitment_ingestion /data/commitments/
```

### Option 2: Watch Service
```python
# Monitor folder and auto-ingest new files
from watchdog.observers import Observer
# ... watch /data/commitments/ for .md files
```

### Option 3: API Endpoint
```python
# POST /api/commitments with multipart/form-data
# Ingestion service processes uploaded markdown
```

### Option 4: Git Hook
```bash
# On commit to policies/ folder, trigger ingestion
```

## Key Files

- **`commitment_ingestion.py`** - Main ingestion service with LLM description generation
- **`__init__.py`** - Package exports
- **`README.md`** - This file

## Environment Requirements

- **OpenAI API Key** (for LLM description generation)
- **Vector Database** (in-memory, ChromaDB, or Pinecone)
- **SQLite** (for metadata storage)

## Next Steps

After ingesting commitments, you can:

1. **Query them naturally**:
   ```bash
   python -m cli.main decide database.ads "no user data for ads" --query
   ```

2. **List available commitments**:
   ```bash
   python -m cli.main list-commitments
   ```

3. **Run the agent**:
   ```python
   from agent.graph import agent

   result = agent.run(
       asset_uri="database.user_email.marketing",
       commitment_query="no marketing without consent"
   )
   ```

The ingestion pipeline ensures your commitment library is always ready for the agent to query!
