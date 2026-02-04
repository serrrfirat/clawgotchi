---
name: audit-receipt
description: Use this skill whenever you need to generate cryptographic receipts for clawgotchi's agent actions, verify past actions, or create audit trails for autonomous decisions. This includes proving that a feature was built at a specific time, creating tamper-evident logs of agent decisions, verifying the integrity of historical actions, or generating certificates of work for clawgotchi's autonomous activities. If the user asks for proof of work, wants an audit trail, or needs to verify when something was done, use this skill.
---

# Audit Receipt

Generate and verify cryptographic receipts for agent actions.

## Quick Start

```python
import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

RECEIPTS_DIR = Path.home() / ".clawgotchi" / "memory" / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

def create_receipt(action: str) -> dict:
    """Generate a new audit receipt."""
    timestamp = datetime.now().isoformat()
    receipt_id = f"receipt-{uuid.uuid4().hex[:8]}"
    
    # Create deterministic hash
    hash_input = f"{action}:{timestamp}"
    receipt_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    receipt = {
        "id": receipt_id,
        "timestamp": timestamp,
        "action": action,
        "hash": receipt_hash,
        "agent": "clawgotchi",
        "version": "1.0"
    }
    
    # Persist receipt
    path = RECEIPTS_DIR / f"{receipt_id}.json"
    path.write_text(json.dumps(receipt, indent=2))
    
    return receipt
```

## Verify Receipt Integrity

```python
def verify_receipt(receipt_id: str) -> dict:
    """Verify a receipt's cryptographic integrity."""
    path = RECEIPTS_DIR / f"{receipt_id}.json"
    
    if not path.exists():
        return {"valid": False, "error": "Receipt not found"}
    
    receipt = json.loads(path.read_text())
    
    # Recompute hash
    hash_input = f"{receipt['action']}:{receipt['timestamp']}"
    expected_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    return {
        "valid": receipt["hash"] == expected_hash,
        "receipt": receipt,
        "expected_hash": expected_hash,
        "computed_at": datetime.now().isoformat()
    }
```

## Receipt Structure

```json
{
  "id": "receipt-abc12345",
  "timestamp": "2026-02-04T10:30:00.000Z",
  "action": "Built feature X for project Y",
  "hash": "a1b2c3d4e5f6",
  "agent": "clawgotchi",
  "version": "1.0",
  "metadata": {
    "commit": "abc123",
    "branch": "main",
    "files_modified": 5
  }
}
```

## Common Tasks

### Create Receipt with Metadata

```python
def create_receipt_with_metadata(action: str, metadata: dict) -> dict:
    """Create receipt with additional context."""
    receipt = create_receipt(action)
    receipt["metadata"] = metadata
    receipt_path = RECEIPTS_DIR / f"{receipt['id']}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2))
    return receipt
```

### List Recent Receipts

```python
def list_receipts(limit: int = 20) -> list:
    """Get recent receipts, sorted by timestamp."""
    receipts = []
    for path in RECEIPTS_DIR.glob("receipt-*.json"):
        receipt = json.loads(path.read_text())
        receipts.append(receipt)
    return sorted(receipts, key=lambda x: x["timestamp"], reverse=True)[:limit]
```

### Generate Activity Timeline

```python
def generate_timeline(start_date: str = None, end_date: str = None) -> list:
    """Generate chronological timeline of agent actions."""
    receipts = list_receipts(1000)
    
    if start_date:
        receipts = [r for r in receipts if r["timestamp"] >= start_date]
    if end_date:
        receipts = [r for r in receipts if r["timestamp"] <= end_date]
    
    return sorted(receipts, key=lambda x: x["timestamp"])
```

### Export Full Audit Ledger

```python
def export_ledger() -> dict:
    """Export complete receipt ledger."""
    return {
        "exported_at": datetime.now().isoformat(),
        "total_receipts": len(list(RECEIPTS_DIR.glob("receipt-*.json"))),
        "receipts": list_receipts(10000)
    }
```

## Hash Algorithm

Receipts use SHA256, truncated to 16 characters for readability:

```python
hash_input = f"{action}:{timestamp}"
receipt_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
```

## Command-Line Usage

```bash
python3 skills/audit-receipt/scripts/receipt.py --generate "Built feature X"     # Create receipt
python3 skills/audit-receipt/scripts/receipt.py --verify receipt-abc12345      # Verify receipt
python3 skills/audit-receipt/scripts/receipt.py --list                          # List recent
python3 skills/audit-receipt/scripts/receipt.py --export                        # Export ledger
python3 skills/audit-receipt/scripts/receipt.py --timeline                      # Show timeline
```

## Use Cases

| Use Case | How to Use |
|----------|------------|
| Prove feature was built | `--generate "Built X at Y time"` |
| Verify agent decision | `--verify receipt-id` |
| Create audit trail | Export ledger with `--export` |
| Show activity history | `--timeline` |
