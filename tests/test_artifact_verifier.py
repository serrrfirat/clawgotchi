"""
Tests for artifact_verifier.py - Content-addressed verification for Clawgotchi artifacts.
Inspired by CID + Ed25519 trust pattern from Quan-AGI.
"""

import pytest
import hashlib
import json
from datetime import datetime
from artifact_verifier import ArtifactVerifier, ArtifactCertificate


class TestArtifactVerifier:
    """Test the ArtifactVerifier class."""
    
    def test_generate_content_hash(self):
        """Content hash should be deterministic."""
        verifier = ArtifactVerifier()
        content = "Hello, Clawgotchi!"
        
        hash1 = verifier._generate_content_hash(content)
        hash2 = verifier._generate_content_hash(content)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex
    
    def test_generate_content_hash_different_inputs(self):
        """Different content should produce different hashes."""
        verifier = ArtifactVerifier()
        
        hash1 = verifier._generate_content_hash("content A")
        hash2 = verifier._generate_content_hash("content B")
        
        assert hash1 != hash2
    
    def test_create_certificate(self):
        """Create a certificate for an artifact."""
        verifier = ArtifactVerifier()
        content = {"message": "test artifact", "type": "feature"}
        
        cert = verifier.create_certificate(content, metadata={"author": "clawgotchi"})
        
        assert isinstance(cert, ArtifactCertificate)
        assert cert.content_hash is not None
        assert cert.creator == "clawgotchi"
        assert cert.metadata["author"] == "clawgotchi"
        assert cert.signature is not None
    
    def test_certificate_verification(self):
        """Verify a certificate is valid."""
        verifier = ArtifactVerifier()
        content = {"test": "data"}
        
        cert = verifier.create_certificate(content)
        is_valid = verifier.verify_certificate(cert, content)
        
        assert is_valid is True
    
    def test_certificate_verification_tampered_content(self):
        """Verification should fail for tampered content."""
        verifier = ArtifactVerifier()
        original_content = {"value": 42}
        
        cert = verifier.create_certificate(original_content)
        
        # Tamper with the content
        tampered_content = {"value": 100}
        is_valid = verifier.verify_certificate(cert, tampered_content)
        
        assert is_valid is False
    
    def test_verify_without_original(self):
        """Can verify just the certificate structure without original content."""
        verifier = ArtifactVerifier()
        content = "Important output"
        
        cert = verifier.create_certificate(content)
        # Verify cert itself is internally consistent
        computed_hash = verifier._generate_content_hash(content)
        
        assert cert.content_hash == computed_hash
    
    def test_serialize_certificate(self):
        """Certificates can be serialized to JSON."""
        verifier = ArtifactVerifier()
        cert = verifier.create_certificate({"test": True})
        
        json_str = cert.to_json()
        restored = ArtifactCertificate.from_json(json_str)
        
        assert restored.content_hash == cert.content_hash
        assert restored.signature == cert.signature
        assert restored.timestamp == cert.timestamp
    
    def test_certificate_str_representation(self):
        """Certificate has a readable string representation."""
        verifier = ArtifactVerifier()
        cert = verifier.create_certificate("test")
        
        repr_str = str(cert)
        assert "ArtifactCertificate" in repr_str
        assert cert.content_hash[:8] in repr_str
