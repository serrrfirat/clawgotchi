"""Tests for StateCheckpoint - Persistent state with change detection."""

import pytest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime

from clawgotchi.resilience.state_checkpoint import (
    StateCheckpoint,
    CheckpointMetadata,
    CheckpointError,
    load_checkpoint,
    save_checkpoint
)


class TestCheckpointMetadata:
    """Test checkpoint metadata handling."""

    def test_create_metadata(self):
        """Create metadata with timestamp and hash."""
        metadata = CheckpointMetadata(
            state_type="memory",
            state_hash="abc123",
            checkpoint_count=1
        )
        assert metadata.state_type == "memory"
        assert metadata.state_hash == "abc123"
        assert metadata.checkpoint_count == 1
        assert metadata.timestamp is not None

    def test_metadata_to_dict(self):
        """Convert metadata to dictionary."""
        metadata = CheckpointMetadata(
            state_type="skills",
            state_hash="def456",
            checkpoint_count=5
        )
        data = metadata.to_dict()
        assert data["state_type"] == "skills"
        assert data["state_hash"] == "def456"
        assert "timestamp" in data


class TestStateCheckpoint:
    """Test StateCheckpoint core functionality."""

    def test_save_and_load_checkpoint(self):
        """Save state and load it back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir)
            state = {"health": 100, "mood": "happy"}
            
            checkpoint.save("session_001", state)
            loaded = checkpoint.load("session_001")
            
            assert loaded == state

    def test_detect_changes(self):
        """Detect when state has changed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir)
            original = {"count": 10}
            
            # Save initial state
            checkpoint.save("task_001", original)
            
            # Modify state
            modified = {"count": 20}
            
            # Checkpoint should detect change
            has_changed = checkpoint.detect_change("task_001", modified)
            assert has_changed is True

    def test_no_change_detection(self):
        """Return False when state unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir)
            state = {"value": "test"}
            
            checkpoint.save("item_001", state)
            has_changed = checkpoint.detect_change("item_001", state)
            
            assert has_changed is False

    def test_list_checkpoints(self):
        """List all saved checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir)
            
            checkpoint.save("session_a", {"data": "A"})
            checkpoint.save("session_b", {"data": "B"})
            checkpoint.save("session_c", {"data": "C"})
            
            checkpoints = checkpoint.list_checkpoints()
            
            assert len(checkpoints) == 3
            assert "session_a" in checkpoints
            assert "session_b" in checkpoints
            assert "session_c" in checkpoints

    def test_delete_checkpoint(self):
        """Delete a checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir)
            
            checkpoint.save("temp_state", {"temp": True})
            assert checkpoint.load("temp_state") == {"temp": True}
            
            checkpoint.delete("temp_state")
            
            # Should raise error when loading deleted
            with pytest.raises(CheckpointError):
                checkpoint.load("temp_state")

    def test_get_hash(self):
        """Verify hash computation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir)
            state = {"key": "value", "number": 42}
            state_hash = checkpoint._compute_hash(state)
            
            # Same state should produce same hash
            hash2 = checkpoint._compute_hash(state)
            assert state_hash == hash2
            
            # Different state should produce different hash
            different_state = {"key": "different"}
            hash3 = checkpoint._compute_hash(different_state)
            assert state_hash != hash3

    def test_checkpoint_with_metadata(self):
        """Save state with custom metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir)
            state = {"progress": 0.75}
            
            checkpoint.save(
                "learning_session",
                state,
                metadata={"learning_rate": 0.01, "epoch": 10}
            )
            
            loaded = checkpoint.load("learning_session")
            assert loaded == state
            
            # Check metadata was stored
            info = checkpoint.get_info("learning_session")
            assert info is not None
            assert info.get("metadata", {}).get("custom_metadata", {}).get("epoch") == 10

    def test_raises_on_nonexistent_load(self):
        """Raise error when loading nonexistent checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir)
            
            with pytest.raises(CheckpointError):
                checkpoint.load("does_not_exist")


class TestLoadSaveFunctions:
    """Test module-level convenience functions."""

    def test_save_checkpoint_function(self):
        """Test save_checkpoint convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_checkpoint(
                tmpdir,
                "quick_save",
                {"status": "done"}
            )
            assert result is True

    def test_load_checkpoint_function(self):
        """Test load_checkpoint convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_checkpoint(tmpdir, "test_load", {"data": 123})
            loaded = load_checkpoint(tmpdir, "test_load")
            
            assert loaded == {"data": 123}
