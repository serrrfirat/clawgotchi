"""StateCheckpoint - Persistent state with change detection.

A lightweight utility for agents to persist state and detect changes
while away. Inspired by page-monitor patterns for infrastructure continuity.
"""

import json
import hashlib
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path


class CheckpointError(Exception):
    """Base exception for checkpoint operations."""
    pass


class CheckpointNotFoundError(CheckpointError):
    """Raised when checkpoint doesn't exist."""
    pass


@dataclass
class CheckpointMetadata:
    """Metadata for a state checkpoint."""
    state_type: str
    state_hash: str
    checkpoint_count: int
    timestamp: str = None
    custom_metadata: Dict = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
        if self.custom_metadata is None:
            self.custom_metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "state_type": self.state_type,
            "state_hash": self.state_hash,
            "checkpoint_count": self.checkpoint_count,
            "timestamp": self.timestamp,
            "custom_metadata": self.custom_metadata
        }


class StateCheckpoint:
    """Manages persistent state checkpoints with change detection."""
    
    def __init__(self, checkpoint_dir: str, state_type: str = "default"):
        """Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoints
            state_type: Type identifier for this state (e.g., "memory", "skills")
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.state_type = state_type
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get path for a checkpoint file."""
        safe_id = checkpoint_id.replace("/", "_").replace(" ", "_")
        return self.checkpoint_dir / f"{safe_id}.json"
    
    def _compute_hash(self, state: Dict[str, Any]) -> str:
        """Compute MD5 hash of state for change detection."""
        state_str = json.dumps(state, sort_keys=True, default=str)
        return hashlib.md5(state_str.encode()).hexdigest()
    
    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Load JSON from file."""
        with open(path, 'r') as f:
            return json.load(f)
    
    def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Save data to JSON file."""
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def save(
        self,
        checkpoint_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict] = None
    ) -> CheckpointMetadata:
        """Save a state checkpoint.
        
        Args:
            checkpoint_id: Unique identifier for this checkpoint
            state: State dictionary to save
            metadata: Optional custom metadata
            
        Returns:
            CheckpointMetadata with save information
        """
        path = self._get_checkpoint_path(checkpoint_id)
        state_hash = self._compute_hash(state)
        
        # Get existing checkpoints count for this state type
        existing = self.list_checkpoints()
        count = len([c for c in existing if checkpoint_id in c])
        
        checkpoint_metadata = CheckpointMetadata(
            state_type=self.state_type,
            state_hash=state_hash,
            checkpoint_count=count + 1,
            custom_metadata=metadata or {}
        )
        
        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "state": state,
            "metadata": checkpoint_metadata.to_dict()
        }
        
        self._save_json(path, checkpoint_data)
        return checkpoint_metadata
    
    def load(self, checkpoint_id: str) -> Dict[str, Any]:
        """Load a state checkpoint.
        
        Args:
            checkpoint_id: Unique identifier for the checkpoint
            
        Returns:
            The saved state dictionary
            
        Raises:
            CheckpointNotFoundError: If checkpoint doesn't exist
        """
        path = self._get_checkpoint_path(checkpoint_id)
        
        if not path.exists():
            raise CheckpointNotFoundError(
                f"Checkpoint '{checkpoint_id}' not found"
            )
        
        data = self._load_json(path)
        return data["state"]
    
    def detect_change(
        self,
        checkpoint_id: str,
        new_state: Dict[str, Any]
    ) -> bool:
        """Detect if state has changed since last checkpoint.
        
        Args:
            checkpoint_id: Checkpoint to compare against
            new_state: Current state to compare
            
        Returns:
            True if state has changed, False if unchanged
        """
        try:
            old_state = self.load(checkpoint_id)
            old_hash = self._compute_hash(old_state)
            new_hash = self._compute_hash(new_state)
            return old_hash != new_hash
        except CheckpointNotFoundError:
            # No checkpoint exists, so by definition it changed
            return True
    
    def list_checkpoints(self) -> List[str]:
        """List all checkpoint IDs.
        
        Returns:
            List of checkpoint identifiers
        """
        checkpoints = []
        for path in self.checkpoint_dir.glob("*.json"):
            # Read just the checkpoint_id from the file
            try:
                data = self._load_json(path)
                if "checkpoint_id" in data:
                    checkpoints.append(data["checkpoint_id"])
            except (json.JSONDecodeError, KeyError):
                continue
        return checkpoints
    
    def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint to delete
            
        Returns:
            True if deleted, False if didn't exist
        """
        path = self._get_checkpoint_path(checkpoint_id)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def get_info(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Get full checkpoint info including metadata.
        
        Args:
            checkpoint_id: Checkpoint to inspect
            
        Returns:
            Dictionary with state and metadata, or None if not found
        """
        path = self._get_checkpoint_path(checkpoint_id)
        if not path.exists():
            return None
        
        return self._load_json(path)


def save_checkpoint(
    checkpoint_dir: str,
    checkpoint_id: str,
    state: Dict[str, Any],
    metadata: Optional[Dict] = None
) -> bool:
    """Convenience function to save a checkpoint.
    
    Args:
        checkpoint_dir: Directory for checkpoints
        checkpoint_id: Unique identifier
        state: State to save
        metadata: Optional metadata
        
    Returns:
        True if successful
    """
    try:
        checkpoint = StateCheckpoint(checkpoint_dir)
        checkpoint.save(checkpoint_id, state, metadata)
        return True
    except Exception:
        return False


def load_checkpoint(
    checkpoint_dir: str,
    checkpoint_id: str
) -> Optional[Dict[str, Any]]:
    """Convenience function to load a checkpoint.
    
    Args:
        checkpoint_dir: Directory for checkpoints
        checkpoint_id: Checkpoint identifier
        
    Returns:
        The saved state, or None if not found
    """
    try:
        checkpoint = StateCheckpoint(checkpoint_dir)
        return checkpoint.load(checkpoint_id)
    except CheckpointNotFoundError:
        return None
