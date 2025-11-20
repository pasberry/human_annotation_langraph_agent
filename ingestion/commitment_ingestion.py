"""
Commitment Ingestion Service

This service processes commitment markdown files and prepares them for the agent:
1. Reads markdown files
2. Uses LLM to generate rich semantic descriptions
3. Chunks documents for RAG
4. Stores in SQLite + Vector DB

This runs SEPARATELY from the agent - it's the ingestion pipeline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage import commitment_search_service, db, embedding_service, rag_service
from storage.schemas import Commitment
from langchain_openai import ChatOpenAI
from config import settings


class CommitmentIngestionService:
    """Service for ingesting and processing commitment documents."""

    def __init__(self):
        """Initialize with LLM for description generation."""
        self.llm = ChatOpenAI(
            model=settings.llm_model_name,
            temperature=0.0  # Deterministic descriptions
        )

    def generate_description(self, commitment_name: str, doc_text: str) -> str:
        """
        Use LLM to generate a rich semantic description of the commitment.

        This description will be used for vector search, so it should:
        - Capture the key prohibitions and permissions
        - Include relevant keywords and concepts
        - Be 1-3 sentences summarizing the policy's intent

        Args:
            commitment_name: Name of the commitment
            doc_text: Full commitment document text

        Returns:
            LLM-generated semantic description
        """
        # Extract first ~2000 characters (enough to understand the policy)
        doc_sample = doc_text[:2000]

        prompt = f"""You are analyzing a data governance policy document.

Policy Name: {commitment_name}

Policy Content (first 2000 characters):
{doc_sample}

Please write a 2-3 sentence semantic description that captures:
1. What data or assets this policy governs
2. The key prohibitions (what's NOT allowed)
3. The key permissions (what IS allowed)

This description will be used for semantic search, so include relevant keywords like:
- Data types (email, phone, personal data, minor data, etc.)
- Prohibited purposes (marketing, advertising, analytics, training, sharing, etc.)
- Permitted purposes (order fulfillment, support, security, compliance, etc.)

Be specific and use the actual terms from the policy.

Description:"""

        try:
            response = self.llm.invoke(prompt)
            description = response.content.strip()
            return description
        except Exception as e:
            print(f"⚠️  LLM description generation failed: {str(e)}")
            # Fallback: use first paragraph from doc
            lines = [line.strip() for line in doc_text.split('\n') if line.strip()]
            for line in lines[1:10]:  # Skip title, look for first content
                if len(line) > 50 and not line.startswith('#') and not line.startswith('-'):
                    return line
            return f"Policy document: {commitment_name}"

    def ingest_commitment(
        self,
        name: str,
        file_path: Path,
        force_regenerate_description: bool = False
    ) -> Commitment:
        """
        Ingest a commitment markdown file.

        Args:
            name: Human-readable name for the commitment
            file_path: Path to markdown file
            force_regenerate_description: If True, regenerate description even if exists

        Returns:
            Ingested commitment object
        """
        print(f"\n📄 Ingesting: {name}")
        print(f"   File: {file_path}")

        # Check if already exists
        existing = db.get_commitment_by_name(name)
        if existing and not force_regenerate_description:
            print(f"   ⚠️  Already exists (ID: {existing.id})")
            print(f"   Use force_regenerate_description=True to regenerate")
            return existing

        # Read markdown file
        with open(file_path, 'r') as f:
            doc_text = f.read()

        print(f"   ✓ Loaded {len(doc_text)} characters")

        # Generate LLM description
        print(f"   🤖 Generating semantic description with LLM...")
        description = self.generate_description(name, doc_text)
        print(f"   ✓ Description: {description[:100]}...")

        # Create or update commitment
        if existing:
            # Update existing
            commitment = existing
            commitment.doc_text = doc_text
            commitment.description = description
            # Note: Would need to implement update method in db
            print(f"   ⚠️  Update not implemented, creating new instead")
            commitment = Commitment(name=name, description=description, doc_text=doc_text)
            db.add_commitment(commitment)
        else:
            # Create new
            commitment = Commitment(
                name=name,
                description=description,
                doc_text=doc_text
            )
            db.add_commitment(commitment)

        print(f"   ✓ Stored in database (ID: {commitment.id})")

        # Chunk and embed for RAG
        print(f"   📦 Chunking document...")
        chunks = rag_service.process_and_store_commitment(commitment)
        print(f"   ✓ Created {len(chunks)} chunks for RAG")

        # Store searchable summary
        print(f"   🔍 Making commitment searchable...")
        commitment_search_service.store_commitment_summary(commitment)
        print(f"   ✓ Commitment summary stored in vector DB")

        print(f"   ✅ Ingestion complete!")

        return commitment

    def ingest_directory(
        self,
        directory: Path,
        pattern: str = "*.md",
        force_regenerate: bool = False
    ) -> list[Commitment]:
        """
        Ingest all markdown files from a directory.

        Args:
            directory: Directory containing commitment markdown files
            pattern: Glob pattern for files (default: *.md)
            force_regenerate: Regenerate descriptions for existing commitments

        Returns:
            List of ingested commitments
        """
        print(f"\n{'='*80}")
        print(f"  BATCH INGESTION: {directory}")
        print(f"{'='*80}\n")

        markdown_files = list(directory.glob(pattern))

        if not markdown_files:
            print(f"❌ No markdown files found matching: {pattern}")
            return []

        print(f"Found {len(markdown_files)} markdown file(s)")

        commitments = []
        for md_file in markdown_files:
            # Generate name from filename
            name = md_file.stem.replace('_', ' ').title()

            try:
                commitment = self.ingest_commitment(
                    name=name,
                    file_path=md_file,
                    force_regenerate_description=force_regenerate
                )
                commitments.append(commitment)
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                continue

        print(f"\n{'='*80}")
        print(f"  ✅ BATCH COMPLETE: {len(commitments)}/{len(markdown_files)} successful")
        print(f"{'='*80}\n")

        return commitments


# Global service instance
commitment_ingestion_service = CommitmentIngestionService()


def main():
    """CLI for commitment ingestion."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest commitment documents into the system"
    )
    parser.add_argument(
        'path',
        type=str,
        help='Path to markdown file or directory'
    )
    parser.add_argument(
        '--name',
        type=str,
        help='Commitment name (only for single file)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration of descriptions'
    )
    parser.add_argument(
        '--pattern',
        type=str,
        default='*.md',
        help='File pattern for directory mode (default: *.md)'
    )

    args = parser.parse_args()
    path = Path(args.path)

    if not path.exists():
        print(f"❌ Path not found: {path}")
        sys.exit(1)

    service = CommitmentIngestionService()

    # Directory mode
    if path.is_dir():
        service.ingest_directory(
            directory=path,
            pattern=args.pattern,
            force_regenerate=args.force
        )

    # Single file mode
    elif path.is_file():
        if not args.name:
            # Generate from filename
            args.name = path.stem.replace('_', ' ').title()

        service.ingest_commitment(
            name=args.name,
            file_path=path,
            force_regenerate_description=args.force
        )

    else:
        print(f"❌ Invalid path: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
