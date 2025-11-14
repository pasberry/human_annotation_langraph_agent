"""Pytest configuration and fixtures."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

# Mock sentence_transformers before any imports that need it
sys.modules['sentence_transformers'] = MagicMock()

from storage.database import Database
from storage.schemas import Commitment


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    db = Database(db_path)
    yield db

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def sample_commitment():
    """Create a sample commitment for testing."""
    return Commitment(
        name="Test SOC 2 CC6.1",
        description="Test commitment for access controls",
        legal_text="""
        SOC 2 Type II - CC6.1: Logical and Physical Access Controls

        The entity implements logical access security software to protect information assets.
        This includes authentication, authorization, and access control mechanisms.

        Production databases containing customer data must have proper access controls.
        Test environments with synthetic data may be excluded.
        """,
        scoping_criteria="""
        IN-SCOPE: Production systems, databases with customer data, authentication systems
        OUT-OF-SCOPE: Test environments, development systems, public data
        """,
        domain="security"
    )


@pytest.fixture
def sample_asset_uri():
    """Sample asset URI for testing."""
    return "asset://database.customer_data.production"


@pytest.fixture
def mock_embedding():
    """Mock embedding vector for testing."""
    return [0.1] * 384  # all-MiniLM-L6-v2 dimension
