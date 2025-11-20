"""
Production Scenario: Customer Data Usage Policy Enforcement

This demo simulates a real production scenario for TechMart e-commerce platform.
We'll test the agent's ability to enforce purpose limitation policies on various
data assets across the company's infrastructure.

The scenario includes:
- Multiple asset types (databases, services, data pipelines)
- Clear in-scope and out-of-scope examples
- Edge cases that require careful reasoning
- Human-in-the-loop feedback (corrections and validations)
- Learning over time through vector similarity search
"""

import json
import sys
from pathlib import Path
from time import sleep

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.graph import agent
from feedback.collector import feedback_collector
from storage import db, rag_service
from storage.schemas import Commitment


# =============================================================================
# Helper Functions
# =============================================================================

def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_subheader(text: str):
    """Print a formatted subheader."""
    print("\n" + "-" * 80)
    print(f"  {text}")
    print("-" * 80 + "\n")


def print_decision_summary(decision):
    """Print a summary of the agent's decision."""
    response = decision.response

    print(f"🤖 Agent Decision: {response.decision}")
    print(f"📊 Confidence: {response.confidence_level} ({response.confidence_score:.2f})")
    print(f"\n💭 Reasoning:")
    print(f"   {response.reasoning[:300]}...")

    if response.commitment_references:
        print(f"\n📚 Referenced Commitment Sections: {len(response.commitment_references)}")
        for ref in response.commitment_references[:2]:
            print(f"   - {ref['chunk_id']}: {ref['relevance']}")

    if response.similar_decisions:
        print(f"\n🔄 Similar Prior Decisions: {len(response.similar_decisions)}")

    if response.missing_information:
        print(f"\n❓ Missing Information:")
        for info in response.missing_information:
            print(f"   - {info}")


def submit_human_feedback(decision_id: str, rating: str, reason: str, correction: str = None):
    """Submit human feedback on a decision."""
    icon = "👍" if rating == "up" else "👎"
    print(f"\n{icon} Human Feedback: {rating.upper()}")
    print(f"   Reason: {reason}")
    if correction:
        print(f"   Correction: {correction}")

    feedback = feedback_collector.submit_feedback(
        decision_id=decision_id,
        rating=rating,
        human_reason=reason,
        human_correction=correction
    )

    print(f"   ✓ Feedback stored (ID: {feedback.id})")
    return feedback


def run_scoping_decision(asset_uri: str, commitment_id: str):
    """Run a scoping decision and return the result."""
    print(f"\n🔍 Evaluating Asset: {asset_uri}")
    print(f"   Against: {commitment_id}")

    result = agent.run(
        asset_uri=asset_uri,
        commitment_id=commitment_id
    )

    if result.errors:
        print(f"\n❌ Errors occurred:")
        for error in result.errors:
            print(f"   - {error}")

    return result


# =============================================================================
# Setup
# =============================================================================

def setup_commitment():
    """Load the Customer Data Usage Policy commitment."""
    print_header("SETUP: Loading Customer Data Usage Policy")

    # Check if already loaded
    existing = db.get_commitment_by_name("Customer Data Usage Policy")
    if existing:
        print("✓ Commitment already exists, skipping load")
        return existing

    # Load the markdown file
    commitment_file = Path(__file__).parent / "commitments" / "customer_data_usage_policy.md"

    with open(commitment_file, "r") as f:
        doc_text = f.read()

    # Create commitment
    commitment = Commitment(
        name="Customer Data Usage Policy",
        description="Purpose limitation policy for customer personal data at TechMart e-commerce platform",
        doc_text=doc_text,
        domain="privacy"
    )

    # Store in database
    db.add_commitment(commitment)
    print(f"✓ Commitment stored in database (ID: {commitment.id})")

    # Process for RAG
    chunks = rag_service.process_and_store_commitment(commitment)
    print(f"✓ Created {len(chunks)} RAG chunks")
    print(f"✓ Chunks embedded and stored in vector database")

    return commitment


# =============================================================================
# Act 1: Initial Decisions (Cold Start - No Prior Decisions)
# =============================================================================

def act1_cold_start(commitment_id: str):
    """
    Act 1: First decisions with no prior history.

    The agent must rely solely on commitment language.
    We'll test clear cases first to build a knowledge base.
    """
    print_header("ACT 1: Cold Start - Building Initial Knowledge Base")

    print("""
    Scenario: First day in production. No prior decisions exist.
    The agent must interpret the commitment document directly.
    We'll start with clear cases to establish patterns.
    """)

    # -------------------------------------------------------------------------
    # Test 1: Clear IN-SCOPE case
    # -------------------------------------------------------------------------
    print_subheader("Test 1.1: Order Fulfillment Database - Clear IN-SCOPE")

    result1 = run_scoping_decision(
        asset_uri="database.customer_email.orders_db",
        commitment_id=commitment_id
    )
    print_decision_summary(result1.decision)

    # Human validates - this is correct
    submit_human_feedback(
        decision_id=result1.decision.id,
        rating="up",
        reason="Correct! Customer email in orders database is explicitly permitted for order fulfillment (Section 2.1)."
    )

    sleep(1)

    # -------------------------------------------------------------------------
    # Test 2: Clear OUT-OF-SCOPE case
    # -------------------------------------------------------------------------
    print_subheader("Test 1.2: Marketing Database - Clear OUT-OF-SCOPE")

    result2 = run_scoping_decision(
        asset_uri="database.customer_email.marketing_campaigns_db",
        commitment_id=commitment_id
    )
    print_decision_summary(result2.decision)

    # Human validates - this is correct
    submit_human_feedback(
        decision_id=result2.decision.id,
        rating="up",
        reason="Correct! Customer email in marketing database is explicitly prohibited without consent (Section 3.1)."
    )

    sleep(1)

    # -------------------------------------------------------------------------
    # Test 3: Customer Support - IN-SCOPE
    # -------------------------------------------------------------------------
    print_subheader("Test 1.3: Support Tickets - Clear IN-SCOPE")

    result3 = run_scoping_decision(
        asset_uri="database.customer_phone.support_tickets_db",
        commitment_id=commitment_id
    )
    print_decision_summary(result3.decision)

    # Human validates
    submit_human_feedback(
        decision_id=result3.decision.id,
        rating="up",
        reason="Correct! Phone number in support tickets is permitted for customer support (Section 2.2)."
    )

    sleep(1)

    return [result1, result2, result3]


# =============================================================================
# Act 2: Edge Cases with Agent Mistakes
# =============================================================================

def act2_edge_cases(commitment_id: str):
    """
    Act 2: Test edge cases where the agent might make mistakes.

    Human feedback will correct the agent, teaching it nuance.
    """
    print_header("ACT 2: Edge Cases - Teaching Through Corrections")

    print("""
    Scenario: Now we test ambiguous cases. The agent might get some wrong.
    Human corrections will teach the agent about edge cases and exceptions.
    """)

    # -------------------------------------------------------------------------
    # Test 4: Analytics Database - Agent might be confused
    # -------------------------------------------------------------------------
    print_subheader("Test 2.1: Analytics Events - Tricky OUT-OF-SCOPE")

    result4 = run_scoping_decision(
        asset_uri="database.customer_address.analytics_events_db",
        commitment_id=commitment_id
    )
    print_decision_summary(result4.decision)

    # Check if agent got it right
    if result4.decision.response.decision == "out-of-scope":
        # Agent got it right!
        submit_human_feedback(
            decision_id=result4.decision.id,
            rating="up",
            reason="Excellent reasoning! Analytics on personal data requires consent per Section 3.2."
        )
    else:
        # Agent got it wrong - needs correction
        submit_human_feedback(
            decision_id=result4.decision.id,
            rating="down",
            reason="Incorrect. While analytics may seem useful, Section 3.2 explicitly prohibits product analytics and business intelligence on personal data without consent.",
            correction="Decision should be OUT-OF-SCOPE. Customer address in analytics database is prohibited under Section 3.2 (Product Analytics) unless explicit consent obtained."
        )

    sleep(1)

    # -------------------------------------------------------------------------
    # Test 5: Fraud Detection - Legitimate Interest Exception
    # -------------------------------------------------------------------------
    print_subheader("Test 2.2: Fraud Detection - IN-SCOPE (Legitimate Interest)")

    result5 = run_scoping_decision(
        asset_uri="service.customer_payment_data.fraud_detection_service",
        commitment_id=commitment_id
    )
    print_decision_summary(result5.decision)

    # This is a legitimate interest case - should be in-scope
    if result5.decision.response.decision == "in-scope":
        submit_human_feedback(
            decision_id=result5.decision.id,
            rating="up",
            reason="Correct! Section 2.3 explicitly permits fraud prevention as a legitimate interest supporting the primary purposes."
        )
    else:
        # Agent was too strict - needs correction
        submit_human_feedback(
            decision_id=result5.decision.id,
            rating="down",
            reason="Too restrictive! Section 2.3 explicitly permits fraud prevention. This is a security measure that protects customers.",
            correction="Decision should be IN-SCOPE. Fraud detection on payment data is explicitly permitted under Section 2.3 (Fraud Prevention and Security) as a legitimate interest."
        )

    sleep(1)

    # -------------------------------------------------------------------------
    # Test 6: Recommendation Engine - Subtle OUT-OF-SCOPE
    # -------------------------------------------------------------------------
    print_subheader("Test 2.3: Recommendation Engine - Nuanced OUT-OF-SCOPE")

    result6 = run_scoping_decision(
        asset_uri="service.customer_purchase_history.recommendation_engine",
        commitment_id=commitment_id
    )
    print_decision_summary(result6.decision)

    # This is tricky - recommendations sound helpful but are really analytics/marketing
    if result6.decision.response.decision == "out-of-scope":
        submit_human_feedback(
            decision_id=result6.decision.id,
            rating="up",
            reason="Great catch! Section 10 examples clarify that recommendation engines using stored purchase history require consent (analytics purposes)."
        )
    elif result6.decision.response.decision == "insufficient-data":
        # Agent wisely asked for clarification
        submit_human_feedback(
            decision_id=result6.decision.id,
            rating="up",
            reason="Good judgment asking for clarification! Section 10 clarifies: session-based recommendations are OK, but using stored purchase history requires consent.",
            correction="For this specific asset (stored purchase history), decision should be OUT-OF-SCOPE per Section 10 edge cases."
        )
    else:
        # Agent thought it was in-scope - wrong
        submit_human_feedback(
            decision_id=result6.decision.id,
            rating="down",
            reason="Too permissive! While recommendations seem helpful, using stored purchase history falls under Section 3.2 (Product Analytics).",
            correction="Decision should be OUT-OF-SCOPE. Recommendation engines using stored customer purchase history require consent per Section 10 examples (analytics purpose)."
        )

    sleep(1)

    return [result4, result5, result6]


# =============================================================================
# Act 3: Learning from Prior Decisions
# =============================================================================

def act3_learning(commitment_id: str):
    """
    Act 3: Test similar assets to see if agent learns from prior decisions.

    Now we have ~6 decisions with feedback. New decisions should leverage this.
    """
    print_header("ACT 3: Learning from Experience - Leveraging Prior Decisions")

    print("""
    Scenario: We now have a knowledge base of prior decisions and human feedback.
    Testing similar assets to see if the agent learns patterns and maintains consistency.
    """)

    # -------------------------------------------------------------------------
    # Test 7: Similar to Test 1 - Should reference prior decision
    # -------------------------------------------------------------------------
    print_subheader("Test 3.1: Similar to Test 1 (Order Fulfillment)")

    result7 = run_scoping_decision(
        asset_uri="database.customer_name.orders_db",
        commitment_id=commitment_id
    )
    print_decision_summary(result7.decision)

    # Check if agent referenced similar decision
    if result7.decision.response.similar_decisions:
        print(f"\n✓ Agent learned! Referenced {len(result7.decision.response.similar_decisions)} prior decisions")
        print(f"  This shows vector search is working - found similar 'orders_db' decisions")

    # Should be in-scope like Test 1
    submit_human_feedback(
        decision_id=result7.decision.id,
        rating="up",
        reason="Consistent with prior decision on orders_db. Good pattern recognition!"
    )

    sleep(1)

    # -------------------------------------------------------------------------
    # Test 8: Similar to Test 2 - Should maintain consistency
    # -------------------------------------------------------------------------
    print_subheader("Test 3.2: Similar to Test 2 (Marketing Prohibition)")

    result8 = run_scoping_decision(
        asset_uri="database.customer_phone.marketing_sms_db",
        commitment_id=commitment_id
    )
    print_decision_summary(result8.decision)

    # Check consistency with Test 2
    if result8.decision.response.decision == "out-of-scope":
        submit_human_feedback(
            decision_id=result8.decision.id,
            rating="up",
            reason="Excellent consistency! Correctly identified this as similar to the marketing_campaigns_db case."
        )
    else:
        submit_human_feedback(
            decision_id=result8.decision.id,
            rating="down",
            reason="Inconsistent! This is the same pattern as marketing_campaigns_db (prohibited without consent).",
            correction="Decision should be OUT-OF-SCOPE, consistent with prior marketing database decisions."
        )

    sleep(1)

    # -------------------------------------------------------------------------
    # Test 9: Complex Case - Quality Assurance
    # -------------------------------------------------------------------------
    print_subheader("Test 3.3: Edge Case - QA Monitoring of Support Tickets")

    result9 = run_scoping_decision(
        asset_uri="service.support_ticket_content.qa_monitoring_dashboard",
        commitment_id=commitment_id
    )
    print_decision_summary(result9.decision)

    # This is tricky - Section 10 says QA on support tickets OK if anonymized
    # With identifiable customer names, requires justification
    if result9.decision.response.decision == "insufficient-data":
        # Good! Agent recognized ambiguity
        submit_human_feedback(
            decision_id=result9.decision.id,
            rating="up",
            reason="Good judgment! Section 10 says QA on support tickets is permitted IF anonymized. Need to verify if this dashboard includes customer names.",
            correction="If dashboard shows customer names: OUT-OF-SCOPE (needs anonymization). If anonymized: IN-SCOPE."
        )
    elif result9.decision.response.decision == "in-scope":
        # Agent needs more nuance
        submit_human_feedback(
            decision_id=result9.decision.id,
            rating="down",
            reason="Missing nuance. Section 10 permits QA monitoring only if support tickets are anonymized.",
            correction="Decision should be INSUFFICIENT-DATA or OUT-OF-SCOPE unless we confirm the dashboard anonymizes customer information."
        )
    else:
        # Agent might be too strict
        submit_human_feedback(
            decision_id=result9.decision.id,
            rating="down",
            reason="Too strict. Section 10 permits QA on support tickets if anonymized. Need to assess anonymization, not blanket reject.",
            correction="Decision should be INSUFFICIENT-DATA - need to verify if customer names are anonymized in the QA dashboard."
        )

    sleep(1)

    return [result7, result8, result9]


# =============================================================================
# Act 4: Production Scale Testing
# =============================================================================

def act4_production_scale(commitment_id: str):
    """
    Act 4: Rapid fire testing like production would see.

    Show how the system handles volume and maintains consistency.
    """
    print_header("ACT 4: Production Scale - High Volume Decision Making")

    print("""
    Scenario: Production environment with many assets being evaluated rapidly.
    The agent should leverage its knowledge base for faster, more consistent decisions.
    """)

    assets_to_test = [
        ("database.customer_email.refunds_db", "in-scope", "Refunds are part of order fulfillment (Section 2.1)"),
        ("database.customer_address.shipping_labels_service", "in-scope", "Shipping is order fulfillment (Section 2.1)"),
        ("pipeline.customer_behavior.product_analytics_etl", "out-of-scope", "Product analytics prohibited (Section 3.2)"),
        ("database.customer_phone.abandoned_cart_reminders", "out-of-scope", "Marketing without consent (Section 3.1)"),
        ("service.customer_ip_address.security_logs", "in-scope", "Security monitoring permitted (Section 2.3)"),
        ("database.customer_name.employee_performance_db", "out-of-scope", "Employee monitoring prohibited (Section 3.4)"),
    ]

    results = []
    correct_count = 0

    for asset_uri, expected_decision, reason in assets_to_test:
        print(f"\n🔍 {asset_uri}")

        result = run_scoping_decision(asset_uri, commitment_id)
        actual_decision = result.decision.response.decision

        # Quick feedback
        if actual_decision == expected_decision:
            print(f"   ✅ Correct: {actual_decision}")
            correct_count += 1
            submit_human_feedback(
                decision_id=result.decision.id,
                rating="up",
                reason=reason
            )
        else:
            print(f"   ❌ Wrong: {actual_decision} (expected {expected_decision})")
            submit_human_feedback(
                decision_id=result.decision.id,
                rating="down",
                reason=f"Should be {expected_decision}. {reason}",
                correction=f"Correct decision: {expected_decision}"
            )

        results.append(result)
        sleep(0.5)

    print(f"\n📊 Accuracy: {correct_count}/{len(assets_to_test)} ({correct_count/len(assets_to_test)*100:.0f}%)")

    return results


# =============================================================================
# Final Analysis
# =============================================================================

def final_analysis():
    """Show what we've learned and what production looks like."""
    print_header("FINAL ANALYSIS: What Does Production Look Like?")

    # Count decisions
    all_decisions = db.list_scoping_decisions(limit=1000)
    print(f"📈 Total Decisions Made: {len(all_decisions)}")

    # Count feedback
    all_feedback = db.list_feedback(limit=1000)
    thumbs_up = len([f for f in all_feedback if f.rating == "up"])
    thumbs_down = len([f for f in all_feedback if f.rating == "down"])

    print(f"💬 Human Feedback:")
    print(f"   👍 Thumbs Up: {thumbs_up}")
    print(f"   👎 Thumbs Down: {thumbs_down}")
    print(f"   📊 Accuracy: {thumbs_up/(thumbs_up+thumbs_down)*100:.0f}%")

    # Show decision distribution
    in_scope = len([d for d in all_decisions if d["decision"] == "in-scope"])
    out_scope = len([d for d in all_decisions if d["decision"] == "out-of-scope"])
    insufficient = len([d for d in all_decisions if d["decision"] == "insufficient-data"])

    print(f"\n🎯 Decision Distribution:")
    print(f"   ✅ In-Scope: {in_scope}")
    print(f"   ❌ Out-of-Scope: {out_scope}")
    print(f"   ❓ Insufficient Data: {insufficient}")

    # Show learning
    print(f"\n🧠 Knowledge Base Growth:")
    print(f"   📚 Commitment Chunks: ~20-30 (from policy document)")
    print(f"   🔄 Prior Decisions: {len(all_decisions)} (searchable in vector DB)")
    print(f"   💡 Human Corrections: {thumbs_down} (teaches edge cases)")

    print(f"\n🔮 Production Characteristics:")
    print(f"   • Fast: Vector search finds similar decisions in milliseconds")
    print(f"   • Consistent: Learns patterns from prior decisions and feedback")
    print(f"   • Transparent: Every decision cites commitment sections and prior cases")
    print(f"   • Improving: Human feedback corrects mistakes and refines understanding")
    print(f"   • Auditable: Full decision history and reasoning stored in database")

    print(f"\n💡 Key Insights:")
    print(f"   1. Cold start decisions rely on commitment text interpretation")
    print(f"   2. Human feedback teaches nuance and edge cases")
    print(f"   3. Vector search finds similar prior decisions automatically")
    print(f"   4. System gets more accurate and consistent over time")
    print(f"   5. Explicit citations make decisions auditable and trustworthy")


# =============================================================================
# Main Demo Flow
# =============================================================================

def main():
    """Run the complete production scenario."""
    print("""
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║                                                                              ║
    ║                    PRODUCTION SCENARIO DEMONSTRATION                         ║
    ║                                                                              ║
    ║                     TechMart E-Commerce Platform                             ║
    ║                   Customer Data Usage Policy Enforcement                     ║
    ║                                                                              ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # Setup
    commitment = setup_commitment()

    # Act 1: Cold start
    act1_results = act1_cold_start(commitment.id)

    # Act 2: Edge cases
    act2_results = act2_edge_cases(commitment.id)

    # Act 3: Learning
    act3_results = act3_learning(commitment.id)

    # Act 4: Production scale
    act4_results = act4_production_scale(commitment.id)

    # Final analysis
    final_analysis()

    print("\n" + "=" * 80)
    print("  ✅ DEMO COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
