"""Tests for AuditReceipt - cryptographic receipts for agent actions."""

import json
import os
import time
import pytest
from datetime import datetime
from unittest.mock import patch, mock_open

# Import the module under test
import sys
sys.path.insert(0, '/workspace')
from audit_receipt import AuditReceipt, ReceiptStore, ReceiptError


class TestAuditReceiptCreation:
    """Test receipt creation and signing."""

    def test_create_receipt_with_minimal_fields(self):
        """Create a receipt with required fields only."""
        receipt = AuditReceipt.create(
            action="test_action",
            payload={"key": "value"}
        )
        assert receipt.action == "test_action"
        assert receipt.payload == {"key": "value"}
        assert receipt.receipt_id is not None
        assert receipt.timestamp is not None
        assert receipt.signature is not None

    def test_create_receipt_with_context(self, tmp_path):
        """Create a receipt with additional context."""
        receipt = AuditReceipt.create(
            action="build_feature",
            payload={"feature": "audit_receipt"},
            context={
                "agent": "clawgotchi",
                "session": "test-session-123"
            }
        )
        assert receipt.context["agent"] == "clawgotchi"
        assert receipt.context["session"] == "test-session-123"

    def test_receipt_id_is_unique(self):
        """Each receipt gets a unique ID."""
        r1 = AuditReceipt.create(action="test", payload={})
        r2 = AuditReceipt.create(action="test", payload={})
        assert r1.receipt_id != r2.receipt_id

    def test_receipt_serialization_roundtrip(self):
        """Receipts can be serialized and deserialized."""
        original = AuditReceipt.create(
            action="serialization_test",
            payload={"data": 123}
        )
        serialized = original.to_dict()
        restored = AuditReceipt.from_dict(serialized)
        assert restored.receipt_id == original.receipt_id
        assert restored.action == original.action
        assert restored.payload == original.payload
        assert restored.signature == original.signature


class TestReceiptVerification:
    """Test receipt verification and tamper detection."""

    def test_receipt_verification_valid(self):
        """A valid receipt verifies correctly."""
        receipt = AuditReceipt.create(
            action="verify_test",
            payload={"test": True}
        )
        assert receipt.verify() is True

    def test_receipt_tampering_detected(self):
        """Tampering with payload invalidates signature."""
        receipt = AuditReceipt.create(
            action="tamper_test",
            payload={"original": True}
        )
        # Tamper with the payload
        receipt.payload = {"original": False, "added": True}
        assert receipt.verify() is False

    def test_receipt_tampering_timestamp_detected(self):
        """Tampering with timestamp invalidates signature."""
        receipt = AuditReceipt.create(
            action="time_tamper",
            payload={}
        )
        # Tamper with the timestamp
        receipt.timestamp = "2099-01-01T00:00:00"
        assert receipt.verify() is False


class TestReceiptStore:
    """Test receipt storage and retrieval."""

    def test_store_receipt(self, tmp_path):
        """Store a receipt in the file system."""
        store_path = tmp_path / "receipts"
        store = ReceiptStore(store_path)

        receipt = AuditReceipt.create(action="store_test", payload={})
        store.save(receipt)

        assert store_path.exists()
        assert (store_path / f"{receipt.receipt_id}.json").exists()

    def test_load_receipt(self, tmp_path):
        """Load a stored receipt."""
        store_path = tmp_path / "receipts"
        store = ReceiptStore(store_path)

        original = AuditReceipt.create(action="load_test", payload={"key": "value"})
        store.save(original)

        loaded = store.load(original.receipt_id)
        assert loaded.receipt_id == original.receipt_id
        assert loaded.payload == original.payload

    def test_check_idempotency_unique(self, tmp_path):
        """New actions are not idempotent."""
        store_path = tmp_path / "receipts"
        store = ReceiptStore(store_path)

        receipt = AuditReceipt.create(action="unique_action", payload={})
        is_duplicate, existing = store.check_idempotency(
            action="unique_action",
            payload_hash=receipt.content_hash
        )
        assert is_duplicate is False
        assert existing is None

    def test_check_idempotency_duplicate(self, tmp_path):
        """Duplicate actions are detected."""
        store_path = tmp_path / "receipts"
        store = ReceiptStore(store_path)

        # Create and store first receipt
        original = AuditReceipt.create(action="repeatable", payload={"id": 123})
        store.save(original)

        # Check for duplicate
        is_duplicate, existing = store.check_idempotency(
            action="repeatable",
            payload_hash=original.content_hash
        )
        assert is_duplicate is True
        assert existing is not None
        assert existing.receipt_id == original.receipt_id

    def test_list_receipts_by_action(self, tmp_path):
        """List receipts filtered by action."""
        store_path = tmp_path / "receipts"
        store = ReceiptStore(store_path)

        # Create multiple receipts with different actions
        r1 = AuditReceipt.create(action="build", payload={})
        r2 = AuditReceipt.create(action="build", payload={})
        r3 = AuditReceipt.create(action="test", payload={})

        store.save(r1)
        store.save(r2)
        store.save(r3)

        build_receipts = store.list_by_action("build")
        assert len(build_receipts) == 2

        test_receipts = store.list_by_action("test")
        assert len(test_receipts) == 1

    def test_get_receipt_stats(self, tmp_path):
        """Get statistics about stored receipts."""
        store_path = tmp_path / "receipts"
        store = ReceiptStore(store_path)

        # Create various receipts
        for i in range(3):
            store.save(AuditReceipt.create(action="build", payload={"n": i}))

        for action in ["build", "test", "deploy"]:
            store.save(AuditReceipt.create(action=action, payload={}))

        stats = store.get_stats()
        assert stats["total_receipts"] == 6
        assert stats["actions"]["build"] == 4  # 3 from loop + 1 extra
        assert "test" in stats["actions"]
        assert "deploy" in stats["actions"]


class TestReceiptErrorHandling:
    """Test error handling."""

    def test_load_nonexistent_receipt_raises(self, tmp_path):
        """Loading a nonexistent receipt raises ReceiptError."""
        store_path = tmp_path / "receipts"
        store = ReceiptStore(store_path)

        with pytest.raises(ReceiptError):
            store.load("nonexistent-receipt-id")

    def test_corrupted_receipt_raises(self, tmp_path):
        """Corrupted receipt file raises ReceiptError."""
        store_path = tmp_path / "receipts"
        store = ReceiptStore(store_path)

        # Write corrupted JSON
        receipt_id = "corrupted-receipt"
        filepath = store_path / f"{receipt_id}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text("{ invalid json }")

        with pytest.raises(ReceiptError):
            store.load(receipt_id)

    def test_tampered_receipt_load_raises(self, tmp_path):
        """Loading a tampered receipt raises ReceiptError."""
        store_path = tmp_path / "receipts"
        store = ReceiptStore(store_path)

        # Create valid receipt
        original = AuditReceipt.create(action="tampered", payload={})
        store.save(original)

        # Tamper with stored file
        filepath = store_path / f"{original.receipt_id}.json"
        data = json.loads(filepath.read_text())
        data["payload"] = {"tampered": True}
        filepath.write_text(json.dumps(data))

        with pytest.raises(ReceiptError):
            store.load(original.receipt_id)
