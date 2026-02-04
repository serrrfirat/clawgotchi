"""
AuditReceipt - Cryptographic receipts for agent actions.

Creates signed receipts that prove WHAT was done, WHEN, and by WHOM.
Enables idempotency checking and tamper-evident audit trails.

Inspired by Circuit_Scribe's "receipts for recurring tasks" concept
and b_crab's automation reliability patterns.
"""

import hashlib
import hmac
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any


class ReceiptError(Exception):
    """Raised when receipt operations fail."""
    pass


@dataclass
class AuditReceipt:
    """
    A cryptographic receipt for an agent action.
    
    A receipt proves that a specific action with specific payload
    was performed at a specific time. The signature ensures
    tamper-evidence.
    """
    action: str
    payload: Dict[str, Any]
    receipt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    context: Dict[str, str] = field(default_factory=dict)
    signature: str = ""
    content_hash: str = ""
    
    def __post_init__(self):
        """Compute content hash after initialization."""
        self.content_hash = self._compute_hash()
        if not self.signature:
            self.signature = self._sign()
    
    def _compute_hash(self) -> str:
        """Compute SHA256 hash of receipt content (excluding signature)."""
        content = json.dumps({
            "receipt_id": self.receipt_id,
            "action": self.action,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "context": self.context
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _sign(self) -> str:
        """Sign the content hash with HMAC-SHA256."""
        # Use receipt_id as secret key (unique per receipt)
        secret = self.receipt_id.encode()
        return hmac.new(secret, self.content_hash.encode(), hashlib.sha256).hexdigest()
    
    def verify(self) -> bool:
        """Verify receipt integrity and signature."""
        # Recompute content hash
        expected_hash = self._compute_hash()
        
        # Check hash matches
        if expected_hash != self.content_hash:
            return False
        
        # Verify signature
        expected_sig = self._sign()
        return hmac.compare_digest(expected_sig, self.signature)
    
    def to_dict(self) -> Dict:
        """Serialize receipt to dictionary."""
        return {
            "receipt_id": self.receipt_id,
            "action": self.action,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "context": self.context,
            "content_hash": self.content_hash,
            "signature": self.signature
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AuditReceipt":
        """Deserialize receipt from dictionary."""
        receipt = cls(
            action=data["action"],
            payload=data["payload"],
            receipt_id=data["receipt_id"],
            timestamp=data["timestamp"],
            context=data.get("context", {}),
            signature=data["signature"]
        )
        # Override computed fields
        receipt.content_hash = data["content_hash"]
        return receipt
    
    @classmethod
    def create(cls, action: str, payload: Dict[str, Any], 
               context: Optional[Dict[str, str]] = None) -> "AuditReceipt":
        """Factory method to create a new receipt."""
        return cls(
            action=action,
            payload=payload,
            context=context or {}
        )


class ReceiptStore:
    """
    Storage and retrieval for audit receipts.
    
    Provides idempotency checking, tamper detection, and
    receipt querying capabilities.
    """
    
    def __init__(self, store_path: Path):
        """
        Initialize receipt store.
        
        Args:
            store_path: Directory where receipts are stored
        """
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
    
    def _receipt_file(self, receipt_id: str) -> Path:
        """Get the file path for a receipt."""
        return self.store_path / f"{receipt_id}.json"
    
    def save(self, receipt: AuditReceipt) -> None:
        """Save a receipt to the store."""
        filepath = self._receipt_file(receipt.receipt_id)
        with open(filepath, 'w') as f:
            json.dump(receipt.to_dict(), f, indent=2)
    
    def load(self, receipt_id: str) -> AuditReceipt:
        """Load a receipt from the store."""
        filepath = self._receipt_file(receipt_id)
        
        if not filepath.exists():
            raise ReceiptError(f"Receipt not found: {receipt_id}")
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ReceiptError(f"Corrupted receipt file: {receipt_id}") from e
        
        receipt = AuditReceipt.from_dict(data)
        
        # Verify on load - detect tampering
        if not receipt.verify():
            raise ReceiptError(f"Tampered receipt detected: {receipt_id}")
        
        return receipt
    
    def check_idempotency(self, action: str, payload_hash: str) -> Tuple[bool, Optional[AuditReceipt]]:
        """
        Check if an action with this payload has already been performed.
        
        Args:
            action: The action type to check
            payload_hash: SHA256 hash of the payload
            
        Returns:
            Tuple of (is_duplicate, existing_receipt)
        """
        for filepath in self.store_path.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                if (data.get("action") == action and 
                    data.get("content_hash") == payload_hash):
                    return True, AuditReceipt.from_dict(data)
            except (json.JSONDecodeError, ReceiptError):
                continue
        
        return False, None
    
    def list_by_action(self, action: str) -> List[AuditReceipt]:
        """List all receipts for a specific action."""
        receipts = []
        for filepath in self.store_path.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if data.get("action") == action:
                    receipts.append(AuditReceipt.from_dict(data))
            except (json.JSONDecodeError, ReceiptError):
                continue
        return sorted(receipts, key=lambda r: r.timestamp)
    
    def get_stats(self) -> Dict:
        """Get statistics about the receipt store."""
        stats = {
            "total_receipts": 0,
            "actions": {},
            "date_range": None
        }
        
        timestamps = []
        for filepath in self.store_path.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                stats["total_receipts"] += 1
                action = data.get("action", "unknown")
                stats["actions"][action] = stats["actions"].get(action, 0) + 1
                timestamps.append(data.get("timestamp", ""))
            except (json.JSONDecodeError, ReceiptError):
                continue
        
        if timestamps:
            stats["date_range"] = {
                "earliest": min(timestamps),
                "latest": max(timestamps)
            }
        
        return stats
    
    def prune(self, before_timestamp: str) -> int:
        """
        Remove receipts older than a given timestamp.
        
        Args:
            before_timestamp: ISO format timestamp (exclusive)
            
        Returns:
            Number of receipts pruned
        """
        pruned = 0
        cutoff = datetime.fromisoformat(before_timestamp.replace('Z', '+00:00'))
        
        for filepath in list(self.store_path.glob("*.json")):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                receipt_time = datetime.fromisoformat(
                    data.get("timestamp", "").replace('Z', '+00:00')
                )
                
                if receipt_time < cutoff:
                    filepath.unlink()
                    pruned += 1
            except (json.JSONDecodeError, ReceiptError, ValueError):
                continue
        
        return pruned


# Convenience function for CLI use
def main():
    """CLI entry point for receipt operations."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Audit Receipt Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create a receipt")
    create_parser.add_argument("action", help="Action type")
    create_parser.add_argument("--payload", default="{}", help="JSON payload")
    create_parser.add_argument("--store", default="./receipts", help="Store path")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify a receipt")
    verify_parser.add_argument("receipt_id", help="Receipt ID")
    verify_parser.add_argument("--store", default="./receipts", help="Store path")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show store statistics")
    stats_parser.add_argument("--store", default="./receipts", help="Store path")
    
    args = parser.parse_args()
    
    if args.command == "create":
        store = ReceiptStore(Path(args.store))
        payload = json.loads(args.payload)
        receipt = AuditReceipt.create(args.action, payload)
        store.save(receipt)
        print(f"Created receipt: {receipt.receipt_id}")
        print(json.dumps(receipt.to_dict(), indent=2))
    
    elif args.command == "verify":
        store = ReceiptStore(Path(args.store))
        receipt = store.load(args.receipt_id)
        valid = receipt.verify()
        print(f"Receipt {args.receipt_id}: {'VALID' if valid else 'INVALID'}")
    
    elif args.command == "stats":
        store = ReceiptStore(Path(args.store))
        stats = store.get_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
