"""
Commitment Search Demo

This demonstrates the new natural language commitment search feature.
Instead of requiring exact commitment IDs, users can query with natural
language and find all relevant commitments automatically.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.graph import agent
from storage import commitment_search_service, db, rag_service
from storage.schemas import Commitment


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


def load_commitments():
    """Load all commitment markdown files."""
    print_header("SETUP: Loading Commitments")

    commitments_dir = Path(__file__).parent / "commitments"
    markdown_files = list(commitments_dir.glob("*.md"))

    loaded = []

    for md_file in markdown_files:
        # Extract name from filename
        name = md_file.stem.replace("_", " ").title()

        # Check if already loaded
        existing = db.get_commitment_by_name(name)
        if existing:
            print(f"✓ {name} (already loaded)")
            loaded.append(existing)
            continue

        # Load the markdown content
        with open(md_file, "r") as f:
            doc_text = f.read()

        # Extract description from markdown (first paragraph after title)
        description = None
        lines = doc_text.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("## Document Information"):
                # Get the next substantial line
                for j in range(i + 1, min(i + 10, len(lines))):
                    if lines[j].strip() and not lines[j].startswith("-") and not lines[j].startswith("**"):
                        description = lines[j].strip()
                        break
                break

        # Create commitment
        commitment = Commitment(
            name=name,
            description=description or f"Policy document: {name}",
            doc_text=doc_text,
            domain="privacy"
        )

        # Store in database
        db.add_commitment(commitment)
        print(f"✓ {name} (loaded)")

        # Process for RAG
        chunks = rag_service.process_and_store_commitment(commitment)
        print(f"  → Created {len(chunks)} RAG chunks")

        # Store summary for search
        commitment_search_service.store_commitment_summary(commitment)
        print(f"  → Stored searchable summary")

        loaded.append(commitment)

    print(f"\n✅ {len(loaded)} commitments ready")
    return loaded


def demo_commitment_search():
    """Demonstrate commitment search with natural language queries."""
    print_header("DEMO: Natural Language Commitment Search")

    queries = [
        "no user data for advertising",
        "no marketing to minors",
        "telemarketing restrictions",
        "phone number usage rules",
    ]

    for query in queries:
        print_subheader(f"Query: \"{query}\"")

        # Search for commitments
        results = commitment_search_service.search_commitments(
            query=query,
            top_k=3,
            score_threshold=0.5
        )

        if results:
            print(f"Found {len(results)} matching commitment(s):\n")
            for idx, commitment in enumerate(results, 1):
                print(f"{idx}. {commitment.name}")
                print(f"   Description: {commitment.description}")
                print()
        else:
            print("No matching commitments found.\n")


def demo_scoping_with_query():
    """Demonstrate scoping decisions using commitment queries."""
    print_header("DEMO: Scoping Decisions with Commitment Queries")

    test_cases = [
        {
            "asset": "database.user_birthdate.marketing_analytics_db",
            "query": "no advertising to minors",
            "expected": "Should find Minor Data Protection policy and flag as OUT-OF-SCOPE"
        },
        {
            "asset": "service.customer_phone.sms_promotional_campaigns",
            "query": "no telemarketing",
            "expected": "Should find Telemarketing Restrictions and flag as OUT-OF-SCOPE"
        },
        {
            "asset": "database.customer_email.order_confirmations_service",
            "query": "transactional communications allowed",
            "expected": "Should find relevant policies and flag as IN-SCOPE"
        }
    ]

    for idx, test in enumerate(test_cases, 1):
        print_subheader(f"Test Case {idx}")
        print(f"Asset: {test['asset']}")
        print(f"Query: \"{test['query']}\"")
        print(f"Expected: {test['expected']}\n")

        try:
            # Run agent with commitment query
            result = agent.run(
                asset_uri=test['asset'],
                commitment_query=test['query']
            )

            if result.errors:
                print("❌ Errors occurred:")
                for error in result.errors:
                    print(f"   - {error}")
                continue

            # Show which commitments were found
            print(f"📚 Commitments Found:")
            print(f"   Primary: {result.commitment.name if result.commitment else 'None'}")
            if result.related_commitments:
                for rc in result.related_commitments:
                    print(f"   Related: {rc.name}")
            print()

            # Show RAG chunks retrieved
            print(f"📄 Retrieved {len(result.rag_chunks)} relevant sections from commitments")
            print()

            # Show decision
            if result.response:
                decision = result.response.decision
                confidence = result.response.confidence_level
                print(f"🤖 Decision: {decision.upper()}")
                print(f"📊 Confidence: {confidence}")
                print(f"\n💭 Reasoning (first 200 chars):")
                print(f"   {result.response.reasoning[:200]}...")
            else:
                print("❌ No response generated")

        except Exception as e:
            print(f"❌ Error: {str(e)}")

        print()


def main():
    """Run the commitment search demonstration."""
    print("""
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║                                                                              ║
    ║                    COMMITMENT SEARCH DEMONSTRATION                           ║
    ║                                                                              ║
    ║                      Natural Language Commitment Discovery                   ║
    ║                                                                              ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # Load commitments
    commitments = load_commitments()

    # Demo 1: Search for commitments
    demo_commitment_search()

    # Demo 2: Use queries in scoping decisions
    demo_scoping_with_query()

    print_header("✅ DEMO COMPLETE")
    print("""
    Key Takeaways:

    1. **Natural Language Queries**: No need to remember exact commitment names
    2. **Automatic Discovery**: System finds all relevant commitments
    3. **Multi-Commitment Decisions**: Combines RAG from multiple policies
    4. **Better Coverage**: Catches requirements across different documents
    5. **User-Friendly**: End users can leverage knowledge without training

    Try it yourself:
        python -m cli.main decide database.user_age.ads "no minor advertising" --query
    """)


if __name__ == "__main__":
    main()
