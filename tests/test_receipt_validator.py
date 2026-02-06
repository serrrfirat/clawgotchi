"""Tests for Receipt Validator - validates agent payment receipts."""
import pytest
import json
from datetime import datetime
import sys
sys.path.insert(0, '.')

from utils.receipt_validator import ReceiptValidator, ReceiptType, SettlementType


@pytest.fixture
def sample_receipt():
    """Valid receipt for testing."""
    return {
        "receipt_version": "0",
        "receipt_id": "01HZWV4K4JQ0P7C6J4RZJ7R6G3",
        "issued_at": "2026-02-06T15:02:00Z",
        "intent_id": "skillsmarket_intent_9f3b",
        "payee": {"address": "0xPayee123456789"},
        "amount": "1.5",
        "currency": "USDC",
        "chain_id": 8453,
        "settlement": {"tx_hash": "0xabc123def456"},
        "task_intent_hash": "0x1234567890abcdef"
    }


@pytest.fixture
def validator(tmp_path):
    """Validator with temp storage."""
    return ReceiptValidator(storage_dir=tmp_path)


class TestReceiptValidation:
    """Test basic receipt validation."""
    
    def test_validate_valid_receipt(self, validator, sample_receipt):
        """Should accept valid receipt."""
        result = validator.validate(sample_receipt)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_reject_missing_required_fields(self, validator):
        """Should reject receipt missing required fields."""
        incomplete = {
            "receipt_id": "test-123",
            "amount": "10"
        }
        result = validator.validate(incomplete)
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_reject_invalid_amount_format(self, validator, sample_receipt):
        """Should reject non-numeric amount."""
        sample_receipt["amount"] = "not-a-number"
        result = validator.validate(sample_receipt)
        assert result.is_valid is False
    
    def test_reject_invalid_currency(self, validator, sample_receipt):
        """Should reject unrecognized currency."""
        sample_receipt["currency"] = "INVALID"
        result = validator.validate(sample_receipt)
        assert result.is_valid is False


class TestHashVerification:
    """Test hash verification functionality."""
    
    def test_verify_task_intent_hash(self, validator, sample_receipt):
        """Should verify task intent hash matches content."""
        # Create receipt with known hash
        sample_receipt["task_intent_hash"] = validator._compute_hash(
            json.dumps({"task": "test"}, sort_keys=True)
        )
        result = validator.verify_hash(sample_receipt, "task_intent_hash")
        assert result is True
    
    def test_hash_mismatch_detection(self, validator, sample_receipt):
        """Should detect hash mismatches."""
        sample_receipt["task_intent_hash"] = "0xwronghash"
        result = validator.verify_hash(sample_receipt, "task_intent_hash")
        assert result is False


class TestSettlementVerification:
    """Test settlement verification."""
    
    def test_verify_onchain_settlement(self, validator, sample_receipt):
        """Should verify on-chain settlement format."""
        result = validator.verify_settlement(sample_receipt["settlement"], "onchain")
        assert result is True
    
    def test_verify_escrow_settlement(self, validator):
        """Should verify escrow settlement format."""
        escrow_settlement = {
            "escrow_id": "agentescrow:0xContract/42",
            "milestone_id": "1"
        }
        result = validator.verify_settlement(escrow_settlement, "escrow")
        assert result is True


class TestReceiptStorage:
    """Test receipt persistence."""
    
    def test_save_and_retrieve_receipt(self, validator, sample_receipt):
        """Should save and retrieve receipt."""
        validator.save(sample_receipt)
        retrieved = validator.get(sample_receipt["receipt_id"])
        assert retrieved is not None
        assert retrieved["receipt_id"] == sample_receipt["receipt_id"]
    
    def test_list_all_receipts(self, validator, sample_receipt):
        """Should list all stored receipts."""
        validator.save(sample_receipt)
        receipts = validator.list_all()
        assert len(receipts) == 1


class TestComplianceReports:
    """Test compliance reporting."""
    
    def test_generate_compliance_report(self, validator, sample_receipt):
        """Should generate compliance report."""
        validator.save(sample_receipt)
        report = validator.generate_compliance_report()
        assert "total_receipts" in report
        assert "by_currency" in report
        assert "by_settlement_type" in report
    
    def test_check_dispute_window(self, validator, sample_receipt):
        """Should check if within dispute window."""
        sample_receipt["dispute_window_seconds"] = 86400
        result = validator.check_dispute_window(sample_receipt)
        assert result is True


class TestReceiptStats:
    """Test receipt statistics."""
    
    def test_get_statistics(self, validator, sample_receipt):
        """Should return receipt statistics."""
        validator.save(sample_receipt)
        stats = validator.get_statistics()
        assert "total_count" in stats
        assert "total_value" in stats
        assert "by_currency" in stats
