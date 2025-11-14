"""Simple standalone schema tests without dependencies."""
import sys
import os

# Add project root to path
sys.path.insert(0, '/home/user/human_annotation_langraph_agent')

# Import directly from schemas module to avoid storage/__init__.py imports
import storage.schemas as schemas
AssetURI = schemas.AssetURI
Commitment = schemas.Commitment
ConfidenceAssessment = schemas.ConfidenceAssessment

def test_asset_uri_parsing():
    """Test parsing asset URIs."""
    uri = "asset://database.customer_data.production"
    asset = AssetURI.from_uri(uri)

    assert asset.asset_type == "database"
    assert asset.asset_descriptor == "customer_data"
    assert asset.asset_domain == "production"
    assert asset.raw_uri == uri
    print("✓ Asset URI parsing test passed")

def test_commitment_creation():
    """Test creating a commitment."""
    commitment = Commitment(
        name="Test Commitment",
        legal_text="This is a test commitment",
        scoping_criteria="Test criteria"
    )

    assert commitment.name == "Test Commitment"
    assert commitment.id is not None
    print("✓ Commitment creation test passed")

def test_confidence_assessment():
    """Test confidence assessment."""
    conf = ConfidenceAssessment(
        level="high",
        score=0.90,
        factors={"rag_quality": 0.4},
        reasoning="High quality RAG match"
    )

    assert conf.level == "high"
    assert conf.score == 0.90
    print("✓ Confidence assessment test passed")

if __name__ == "__main__":
    test_asset_uri_parsing()
    test_commitment_creation()
    test_confidence_assessment()
    print("\n✅ All simple schema tests passed!")
