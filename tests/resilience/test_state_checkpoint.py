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
    
    def test_metadata_default_timestamp(self):
        """Test that timestamp is set automatically."""
        meta = CheckpointMetadata(
            state_type="test",
            state_hash="abc123",
            checkpoint_count=1
        )
        assert meta.timestamp is not None
        assert "T" in meta.timestamp  # ISO format contains T
    
    def test_metadata_to_dict(self):
        """Test metadata converts to dictionary correctly."""
        meta = CheckpointMetadata(
            state_type="test",
            state_hash="abc123",
            checkpoint_count=1,
            custom_metadata={"key": "value"}
        )
        data = meta.to_dict()
        
        assert data["state_type"] == "test"
        assert data["state_hash"] == "abc123"
        assert data["checkpoint_count"] == 1
        assert data["custom_metadata"]["key"] == "value"


class TestStateCheckpoint:
    """Test StateCheckpoint core functionality."""
    
    def test_init_creates_checkpoint_dir(self):
        """Test that initialization creates the checkpoint directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_dir = os.path.join(tmpdir, "checkpoints")
            checkpoint = StateCheckpoint(checkpoint_dir, "test")
            assert os.path.exists(checkpoint_dir)
    
    def test_save_and_load_checkpoint(self):
        """Test saving and loading a simple checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir, "test")
            original_state = {"key": "value"}
            checkpoint.save("test_id", original_state)
            
            loaded_state = checkpoint.load("test_id")
            assert loaded_state == original_state
    
    def test_detect_changes(self):
        """Test change detection returns True when state changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir, "test")
            checkpoint.save("test_id", {"version": 1})
            
            has_changed = checkpoint.detect_change("test_id", {"version": 2})
            assert has_changed == True
    
    def test_no_change_detection(self):
        """Test change detection returns False when state unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir, "test")
            original = {"version": 1, "data": "same"}
            checkpoint.save("test_id", original)
            
            has_changed = checkpoint.detect_change("test_id", original)
            assert has_changed == False
    
    def test_list_checkpoints(self):
        """Test listing all checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir, "test")
            checkpoint.save("id1", {"v": 1})
            checkpoint.save("id2", {"v": 2})
            checkpoint.save("id3", {"v": 3})
            
            checkpoints = checkpoint.list_checkpoints()
            assert len(checkpoints) == 3
            assert "id1" in checkpoints
            assert "id2" in checkpoints
            assert "id3" in checkpoints
    
    def test_delete_checkpoint(self):
        """Test deleting an existing checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir, "test")
            checkpoint.save("test_id", {"v": 1})
            
            result = checkpoint.delete("test_id")
            assert result == True
            
            path = checkpoint._get_checkpoint_path("test_id")
            assert not path.exists()
    
    def test_get_hash(self):
        """Test that same state produces same hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir, "test")
            state = {"key": "value"}
            
            hash1 = checkpoint._compute_hash(state)
            hash2 = checkpoint._compute_hash(state)
            assert hash1 == hash2
    
    def test_checkpoint_with_metadata(self):
        """Test saving with custom metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir, "test")
            custom_meta = {"author": "test", "version": "1.0"}
            metadata = checkpoint.save("test_id", {"key": "value"}, custom_meta)
            
            assert metadata.custom_metadata == custom_meta
            assert metadata.custom_metadata["author"] == "test"
    
    def test_raises_on_nonexistent_load(self):
        """Test that loading nonexistent checkpoint raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = StateCheckpoint(tmpdir, "test")
            
            with pytest.raises(Exception):  # CheckpointNotFoundError
                checkpoint.load("nonexistent")


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_save_checkpoint_function(self):
        """Test save_checkpoint convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_checkpoint(tmpdir, "test_id", {"key": "value"})
            assert result == True
    
    def test_load_checkpoint_function(self):
        """Test load_checkpoint convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_checkpoint(tmpdir, "test_id", {"key": "value"})
            state = load_checkpoint(tmpdir, "test_id")
            assert state == {"key": "value"}
