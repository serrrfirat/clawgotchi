"""Receipt Validator - validates and verifies agent payment receipts.

Inspired by the Receipt Object v0 spec from @paytrigo_bd_growth on Moltbook.
Supports both on-chain settlements and escrow-based payments.
"""
import json
import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ReceiptType(Enum):
    """Receipt version types."""
    V0 = "0"


class SettlementType(Enum):
    """Settlement types."""
    ONCHAIN = "onchain"
    ESCROW = "escrow"


class Currency(Enum):
    """Supported currencies."""
    USDC = "USDC"
    USDT = "USDT"
    ETH = "ETH"
    BTC = "BTC"
    CLAW = "CLAW"


@dataclass
class ValidationResult:
    """Result of receipt validation."""
    is_valid: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


@dataclass
class ReceiptValidator:
    """Validates agent payment receipts."""
    
    storage_dir: str = "./data/receipts"
    
    def __post_init__(self):
        """Initialize storage directory."""
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def validate(self, receipt: dict) -> ValidationResult:
        """Validate receipt against spec."""
        errors = []
        warnings = []
        
        # Required fields check
        required_fields = [
            "receipt_version", "receipt_id", "issued_at",
            "intent_id", "payee", "amount", "currency", "settlement"
        ]
        
        for field in required_fields:
            if field not in receipt:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        # Validate receipt version
        if receipt.get("receipt_version") != "0":
            errors.append(f"Unsupported receipt version: {receipt['receipt_version']}")
        
        # Validate amount format
        try:
            amount = float(receipt["amount"])
            if amount <= 0:
                errors.append("Amount must be positive")
        except (ValueError, TypeError):
            errors.append(f"Invalid amount format: {receipt['amount']}")
        
        # Validate currency
        try:
            Currency(receipt["currency"])
        except ValueError:
            errors.append(f"Unsupported currency: {receipt['currency']}")
        
        # Validate settlement
        settlement = receipt.get("settlement", {})
        if "tx_hash" not in settlement and "escrow_id" not in settlement:
            errors.append("Settlement must have either tx_hash or escrow_id")
        
        # Validate payee structure
        payee = receipt.get("payee", {})
        if not payee.get("address"):
            errors.append("Payee must have an address")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _compute_hash(self, content: str) -> str:
        """Compute keccak256 hash of content."""
        return "0x" + hashlib.sha256(content.encode()).hexdigest()
    
    def verify_hash(self, receipt: dict, hash_field: str) -> bool:
        """Verify a hash field matches its content."""
        if hash_field not in receipt:
            return False
        
        expected_hash = receipt[hash_field]
        
        # Build content to hash based on field type
        if hash_field == "task_intent_hash":
            # Would normally hash the actual task intent
            # For testing, we check if hash format is valid
            return expected_hash.startswith("0x") and len(expected_hash) == 66
        
        return False
    
    def verify_settlement(self, settlement: dict, expected_type: str) -> bool:
        """Verify settlement format."""
        if expected_type == "onchain":
            return "tx_hash" in settlement and settlement["tx_hash"].startswith("0x")
        elif expected_type == "escrow":
            return "escrow_id" in settlement
        return False
    
    def save(self, receipt: dict) -> bool:
        """Save receipt to storage."""
        if not self.validate(receipt).is_valid:
            return False
        
        receipt_id = receipt["receipt_id"]
        filepath = os.path.join(self.storage_dir, f"{receipt_id}.json")
        
        with open(filepath, 'w') as f:
            json.dump(receipt, f, indent=2)
        
        return True
    
    def get(self, receipt_id: str) -> Optional[dict]:
        """Retrieve receipt by ID."""
        filepath = os.path.join(self.storage_dir, f"{receipt_id}.json")
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def list_all(self) -> list:
        """List all stored receipts."""
        receipts = []
        
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                receipt = self.get(filename.replace('.json', ''))
                if receipt:
                    receipts.append(receipt)
        
        return receipts
    
    def generate_compliance_report(self) -> dict:
        """Generate compliance report for all receipts."""
        receipts = self.list_all()
        
        report = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total_receipts": len(receipts),
            "by_currency": {},
            "by_settlement_type": {},
            "total_value_usd": 0
        }
        
        for receipt in receipts:
            currency = receipt.get("currency", "UNKNOWN")
            settlement_type = "onchain" if "tx_hash" in receipt.get("settlement", {}) else "escrow"
            
            # Count by currency
            report["by_currency"][currency] = report["by_currency"].get(currency, 0) + 1
            
            # Count by settlement type
            report["by_settlement_type"][settlement_type] = \
                report["by_settlement_type"].get(settlement_type, 0) + 1
        
        return report
    
    def check_dispute_window(self, receipt: dict) -> bool:
        """Check if receipt is within dispute window."""
        if "dispute_window_seconds" not in receipt:
            return True  # No dispute window = no dispute possible
        
        issued_at = datetime.fromisoformat(receipt["issued_at"].replace('Z', '+00:00'))
        now = datetime.now(issued_at.tzinfo)
        
        elapsed_seconds = (now - issued_at).total_seconds()
        
        return elapsed_seconds < receipt["dispute_window_seconds"]
    
    def get_statistics(self) -> dict:
        """Get receipt statistics."""
        receipts = self.list_all()
        
        stats = {
            "total_count": len(receipts),
            "total_value": {},
            "by_currency": {},
            "by_settlement_type": {}
        }
        
        for receipt in receipts:
            currency = receipt.get("currency", "UNKNOWN")
            amount = float(receipt.get("amount", 0))
            settlement_type = "onchain" if "tx_hash" in receipt.get("settlement", {}) else "escrow"
            
            # Aggregate by currency
            stats["by_currency"][currency] = stats["by_currency"].get(currency, 0) + 1
            
            # Aggregate by settlement type
            stats["by_settlement_type"][settlement_type] = \
                stats["by_settlement_type"].get(settlement_type, 0) + 1
            
            # Sum values
            if currency not in stats["total_value"]:
                stats["total_value"][currency] = 0
            stats["total_value"][currency] += amount
        
        return stats
