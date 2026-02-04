---
name: audit-receipt
description: Generate and verify cryptographic receipts for clawgotchi's agent actions. Use when proving work was done, verifying agent decisions, or creating audit trails for autonomous actions.
---

# Audit Receipt

Generate verifiable receipts for agent actions.

## Commands

```bash
python3 skills/audit-receipt/scripts/receipt.py --generate "description"  # Create receipt
python3 skills/audit-receipt/scripts/receipt.py --verify RECEIPT_ID       # Verify receipt
python3 skills/audit-receipt/scripts/receipt.py --list                    # List receipts
python3 skills/audit-receipt/scripts/receipt.py --export                  # Export ledger
```

## Receipt Structure

```json
{
  "id": "receipt-uuid",
  "timestamp": "ISO8601",
  "action": "what was done",
  "hash": "SHA256 of action+timestamp",
  "signature": "agent signature"
}
```

## Use Cases

- Prove feature was built at specific time
- Verify agent decision timeline
- Create audit trail for autonomous actions
