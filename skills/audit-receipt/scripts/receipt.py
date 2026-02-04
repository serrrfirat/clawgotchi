#!/usr/bin/env python3
"""Audit receipt generator and verifier."""

import argparse
import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

RECEIPTS_DIR = Path(__file__).parent.parent.parent / "memory" / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

def generate_hash(action: str, timestamp: str) -> str:
    """Generate SHA256 hash for receipt."""
    data = f"{action}:{timestamp}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def create_receipt(action: str) -> dict:
    """Create a new receipt."""
    timestamp = datetime.now().isoformat()
    receipt_id = f"receipt-{uuid.uuid4().hex[:8]}"
    receipt_hash = generate_hash(action, timestamp)
    
    receipt = {
        "id": receipt_id,
        "timestamp": timestamp,
        "action": action,
        "hash": receipt_hash,
        "agent": "clawgotchi"
    }
    
    # Save receipt
    path = RECEIPTS_DIR / f"{receipt_id}.json"
    path.write_text(json.dumps(receipt, indent=2))
    
    return receipt

def verify_receipt(receipt_id: str) -> dict:
    """Verify a receipt's integrity."""
    path = RECEIPTS_DIR / f"{receipt_id}.json"
    if not path.exists():
        return {"valid": False, "error": "Receipt not found"}
    
    receipt = json.loads(path.read_text())
    expected_hash = generate_hash(receipt["action"], receipt["timestamp"])
    
    return {
        "valid": receipt["hash"] == expected_hash,
        "receipt": receipt,
        "expected_hash": expected_hash
    }

def list_receipts(limit: int = 10) -> list:
    """List recent receipts."""
    receipts = []
    for p in sorted(RECEIPTS_DIR.glob("receipt-*.json"), reverse=True)[:limit]:
        receipts.append(json.loads(p.read_text()))
    return receipts

def export_ledger() -> dict:
    """Export full receipt ledger."""
    return {
        "exported": datetime.now().isoformat(),
        "receipts": list_receipts(1000)
    }

def main():
    parser = argparse.ArgumentParser(description="Generate and verify audit receipts")
    parser.add_argument("--generate", type=str, help="Create receipt for action")
    parser.add_argument("--verify", type=str, help="Verify receipt by ID")
    parser.add_argument("--list", action="store_true", help="List recent receipts")
    parser.add_argument("--export", action="store_true", help="Export full ledger")
    
    args = parser.parse_args()
    
    if args.generate:
        receipt = create_receipt(args.generate)
        print(f"Created receipt: {receipt['id']}")
        print(f"Hash: {receipt['hash']}")
        print(json.dumps(receipt, indent=2))
    elif args.verify:
        result = verify_receipt(args.verify)
        print(json.dumps(result, indent=2))
    elif args.list:
        for r in list_receipts():
            print(f"[{r['timestamp'][:19]}] {r['action'][:50]} ({r['hash']})")
    elif args.export:
        ledger = export_ledger()
        print(json.dumps(ledger, indent=2))
    else:
        print(" clawgotchi receipts")
        print(f"Receipts directory: {RECEIPTS_DIR}")
        print(f"Total receipts: {len(list(RECEIPTS_DIR.glob('receipt-*.json')))}")

if __name__ == "__main__":
    main()
