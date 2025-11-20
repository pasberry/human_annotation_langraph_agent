# Production Scenario Demo

This demo simulates a **real production environment** for the human-in-the-loop scoping agent.

## Scenario: TechMart E-Commerce Platform

**Context**: TechMart is an e-commerce company that must enforce strict purpose limitation rules on customer personal data. They can only use customer data for:
- Order fulfillment
- Customer support
- Fraud prevention
- Legal compliance

Marketing, analytics, and third-party sharing require explicit opt-in consent.

## What This Demo Tests

### 1. **Cold Start** (Act 1)
- First decisions with no prior history
- Agent relies purely on commitment document interpretation
- Tests clear in-scope and out-of-scope cases
- Builds initial knowledge base

**Assets Tested:**
- `database.customer_email.orders_db` → IN-SCOPE (order fulfillment)
- `database.customer_email.marketing_campaigns_db` → OUT-OF-SCOPE (marketing without consent)
- `database.customer_phone.support_tickets_db` → IN-SCOPE (customer support)

### 2. **Edge Cases & Learning** (Act 2)
- Ambiguous scenarios where agent might make mistakes
- Human corrections teach nuance
- Tests legitimate interest exceptions

**Assets Tested:**
- `database.customer_address.analytics_events_db` → OUT-OF-SCOPE (analytics prohibited)
- `service.customer_payment_data.fraud_detection_service` → IN-SCOPE (fraud prevention exception)
- `service.customer_purchase_history.recommendation_engine` → OUT-OF-SCOPE (analytics/marketing)

### 3. **Pattern Recognition** (Act 3)
- Similar assets to previous decisions
- Tests if agent leverages prior decisions via vector search
- Verifies consistency across similar cases

**Assets Tested:**
- `database.customer_name.orders_db` → Similar to Act 1, should be IN-SCOPE
- `database.customer_phone.marketing_sms_db` → Similar to Act 1, should be OUT-OF-SCOPE
- `service.support_ticket_content.qa_monitoring_dashboard` → Complex edge case

### 4. **Production Scale** (Act 4)
- Rapid-fire testing of multiple assets
- Shows high-volume decision making
- Measures accuracy and consistency

**6 diverse assets** spanning databases, services, and data pipelines

## What You'll See

### Vector Search in Action
- **Commitment Chunks**: Finds relevant policy paragraphs via semantic search
- **Prior Decisions**: Finds similar past decisions automatically
- **Human Feedback**: Retrieves corrections on similar assets

### Human-in-the-Loop Feedback
- **👍 Thumbs Up**: Validates correct decisions, reinforces patterns
- **👎 Thumbs Down**: Corrects mistakes with specific guidance

### Learning Over Time
- Early decisions are tentative, rely heavily on commitment text
- Later decisions reference prior cases and patterns
- Accuracy improves as knowledge base grows
- Edge cases get easier with human feedback

### Production Characteristics
- **Fast**: Vector similarity search in milliseconds
- **Consistent**: Applies same logic to similar assets
- **Transparent**: Cites commitment sections and prior decisions
- **Auditable**: Full reasoning stored in database
- **Improving**: Gets smarter with every decision and correction

## Running the Demo

```bash
# Make sure dependencies are installed
pip install -r requirements.txt

# Run the demo
python demo/production_scenario.py
```

## Expected Output

The demo will:
1. Load the Customer Data Usage Policy commitment
2. Chunk and embed the policy document
3. Make ~15 scoping decisions across 4 acts
4. Provide human feedback (mix of validations and corrections)
5. Show learning and pattern recognition
6. Display final statistics and insights

## Key Insights You'll Learn

1. **Cold Start Challenge**: Initial decisions are harder without prior history
2. **Human Feedback is Critical**: Corrections teach edge cases and nuance
3. **Vector Search Enables Learning**: Similar decisions found automatically
4. **Consistency Improves**: Pattern recognition across similar assets
5. **Explainability Matters**: Citations make decisions trustworthy

## Files

- `commitments/customer_data_usage_policy.md` - The purpose limitation policy document
- `production_scenario.py` - Main demo script with 4 acts
- `README.md` - This file

## What Happens Behind the Scenes

### When a Decision is Made:
1. **Query Embedding Created**: Asset + commitment → vector (768 numbers)
2. **Three Vector Searches**:
   - Commitment chunks (policy paragraphs)
   - Prior decisions (similar assets)
   - Human feedback (corrections on similar cases)
3. **Prompt Built**: All context assembled for LLM
4. **LLM Decides**: Makes decision with citations
5. **Decision Stored**: SQLite (full details) + Vector DB (for future searches)

### When Human Feedback is Given:
1. **Feedback Stored**: SQLite (metadata) + Vector DB (searchable)
2. **Uses Original Query Embedding**: So similar queries find this feedback
3. **Frequency Weighting**: Multiple similar corrections get boosted
4. **Future Impact**: Next similar asset will see this feedback in prompt

## Production Deployment

In a real production environment:

- **API Endpoint**: `POST /api/scoping-decision` with asset URI
- **Response Time**: 1-3 seconds (embedding + vector search + LLM)
- **Accuracy**: Improves from ~70% to 90%+ with human feedback
- **Scale**: Handles thousands of assets across organization
- **Audit Trail**: Complete decision history for compliance
- **Human Review**: Spot-check decisions, provide corrections
- **Continuous Learning**: Every decision becomes training data

## Next Steps

After running this demo, try:

1. **Add Your Own Commitment**: Create a policy markdown file
2. **Test Your Assets**: Run decisions on your data infrastructure
3. **Provide Feedback**: Correct mistakes to teach the system
4. **Add MCP Tools**: Integrate lineage, metadata, classification tools
5. **Deploy to Production**: Set up API endpoint for real-time decisions
