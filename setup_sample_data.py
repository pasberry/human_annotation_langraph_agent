"""Setup script to load sample commitment data."""
import sys
from pathlib import Path

from storage import db, rag_service
from storage.schemas import Commitment


def setup_sample_commitments():
    """Load sample commitments into the database."""
    print("Loading sample commitments...\n")

    sample_data_dir = Path("sample_data")

    commitments_to_add = [
        {
            "name": "SOC 2 Type II - CC6.1",
            "description": "Logical and Physical Access Controls",
            "file": sample_data_dir / "soc2_cc6.1.txt",
            "domain": "security"
        },
        {
            "name": "GDPR Article 5",
            "description": "Principles Relating to Processing of Personal Data",
            "file": sample_data_dir / "gdpr_article5.txt",
            "domain": "privacy"
        }
    ]

    for commitment_info in commitments_to_add:
        print(f"Adding: {commitment_info['name']}")

        # Check if already exists
        existing = db.get_commitment_by_name(commitment_info["name"])
        if existing:
            print(f"  ⚠️  Already exists, skipping\n")
            continue

        # Read legal text
        with open(commitment_info["file"], "r") as f:
            legal_text = f.read()

        # Split into legal text and scoping criteria
        parts = legal_text.split("Scoping Considerations:")
        main_text = parts[0].strip()
        scoping_criteria = parts[1].strip() if len(parts) > 1 else None

        # Create commitment
        commitment = Commitment(
            name=commitment_info["name"],
            description=commitment_info["description"],
            legal_text=main_text,
            scoping_criteria=scoping_criteria,
            domain=commitment_info["domain"]
        )

        # Add to database
        db.add_commitment(commitment)
        print(f"  ✓ Added to database")

        # Process for RAG
        chunks = rag_service.process_and_store_commitment(commitment)
        print(f"  ✓ Created {len(chunks)} RAG chunks\n")

    print("✅ Sample data setup complete!\n")
    print("Available commitments:")
    for c in db.list_commitments():
        print(f"  - {c.name}")


if __name__ == "__main__":
    setup_sample_commitments()
