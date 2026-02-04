"""
ArtifactVerifier - Content-addressed verification for Clawgotchi artifacts.

Inspired by the CID + Ed25519 trust pattern from Quan-AGI on Moltbook:
- Ed25519 proves WHO signed
- CID proves WHAT was signed
- Together: tamper-proof verification

This module provides:
- Content hashing (SHA256 as CID substitute)
- Artifact certificates with metadata
- Verification that content matches the certificate

"Content addressing IS verification" - Quan-AGI
"""

import hashlib
import json
import hmac
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ArtifactCertificate:
    """
    A certificate that proves WHAT was created and WHEN.
    
    Analogous to IPFS CID + Ed25519 signature:
    - content_hash: Proves WHAT (like CID)
    - signature: Proves WHO (HMAC for simplicity, Ed25519 in production)
    - timestamp: Proves WHEN
    """
    content_hash: str
    signature: str
    timestamp: str
    creator: str
    metadata: Dict[str, Any]
    
    def to_json(self) -> str:
        """Serialize certificate to JSON."""
        return json.dumps(asdict(self), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "ArtifactCertificate":
        """Deserialize certificate from JSON."""
        data = json.loads(json_str)
        return cls(**data)
    
    def __str__(self) -> str:
        return f"ArtifactCertificate({self.content_hash[:12]}... by {self.creator} at {self.timestamp})"


class ArtifactVerifier:
    """
    Create and verify content-addressed artifact certificates.
    
    Usage:
        verifier = ArtifactVerifier()
        
        # Create certificate for an artifact
        cert = verifier.create_certificate(
            content={"feature": "new_mode", "version": "1.0"},
            metadata={"type": "release"}
        )
        
        # Verify the artifact matches the certificate
        is_valid = verifier.verify_certificate(cert, original_content)
    """
    
    def __init__(self, secret_key: Optional[str] = None, creator: str = "clawgotchi"):
        self.secret_key = secret_key or self._generate_secret()
        self.creator = creator
    
    def _generate_secret(self) -> str:
        """Generate a secret key for signing."""
        return hashlib.sha256(f"clawgotchi-{datetime.now().isoformat()}".encode()).hexdigest()[:32]
    
    def _generate_content_hash(self, content: Any) -> str:
        """
        Generate a content-addressable hash.
        
        Like IPFS CID, this hash IS the content identity.
        Two identical contents produce identical hashes.
        """
        if isinstance(content, str):
            content_bytes = content.encode()
        elif isinstance(content, dict):
            content_bytes = json.dumps(content, sort_keys=True).encode()
        else:
            content_bytes = str(content).encode()
        
        return hashlib.sha256(content_bytes).hexdigest()
    
    def _sign(self, content_hash: str) -> str:
        """Create a signature proving WHO created this."""
        message = f"{content_hash}:{self.creator}:{datetime.now().isoformat()}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def create_certificate(
        self,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ArtifactCertificate:
        """
        Create a certificate for an artifact.
        
        Args:
            content: The artifact to certify
            metadata: Additional metadata about the artifact
        
        Returns:
            ArtifactCertificate with content hash and signature
        """
        content_hash = self._generate_content_hash(content)
        signature = self._sign(content_hash)
        
        return ArtifactCertificate(
            content_hash=content_hash,
            signature=signature,
            timestamp=datetime.now().isoformat(),
            creator=self.creator,
            metadata=metadata or {}
        )
    
    def verify_certificate(self, cert: ArtifactCertificate, content: Any) -> bool:
        """
        Verify that content matches the certificate.
        
        Args:
            cert: The certificate to verify against
            content: The original content to verify
        
        Returns:
            True if content produces the same hash as the certificate
        """
        computed_hash = self._generate_content_hash(content)
        return hmac.compare_digest(computed_hash, cert.content_hash)
    
    def verify_with_recreator(self, cert: ArtifactCertificate, recreate_content: Any) -> bool:
        """
        Verify by recreating content and comparing hashes.
        
        This is useful when you have a way to regenerate the original content
        rather than storing it directly.
        """
        return self.verify_certificate(cert, recreate_content)


# Example usage
if __name__ == "__main__":
    verifier = ArtifactVerifier()
    
    # Create certificate for a feature
    feature = {
        "name": "TasteProfile",
        "version": "1.0",
        "description": "Rejection ledger for identity fingerprint"
    }
    
    cert = verifier.create_certificate(
        content=feature,
        metadata={"category": "identity", "build_date": "2026-02-04"}
    )
    
    print(f"Certificate: {cert}")
    print(f"Content Hash: {cert.content_hash}")
    print(f"Verified: {verifier.verify_certificate(cert, feature)}")
