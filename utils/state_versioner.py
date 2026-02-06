"""State Versioner - Version tracking for agent state snapshots.

Provides utilities to:
- Save current state as a versioned backup
- List all available versions
- Restore from a specific version
- Get the latest version
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any


# Paths - can be overridden for testing
STATE_DIR = os.environ.get('CLAWGOTCHI_STATE_DIR', 'memory')
BACKUPS_DIR = os.environ.get('CLAWGOTCHI_BACKUPS_DIR', os.path.join(STATE_DIR, 'backups'))


def save_version(state_dict: Dict[str, Any]) -> str:
    """Save the current state as a new versioned backup.
    
    Args:
        state_dict: The agent state dictionary to save
        
    Returns:
        The filename of the created backup
    """
    now = datetime.now()
    timestamp = now.strftime('%Y%m%d_%H%M%S')
    filename = f"state_{timestamp}.json"
    filepath = os.path.join(BACKUPS_DIR, filename)
    
    # Ensure backups directory exists
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    
    with open(filepath, 'w') as f:
        json.dump(state_dict, f, indent=2)
    
    return filename


def list_versions() -> List[Dict[str, Any]]:
    """List all available versions with metadata.
    
    Returns:
        List of dicts with 'filename', 'timestamp', and 'size' keys
    """
    versions = []
    
    if not os.path.exists(BACKUPS_DIR):
        return []
    
    for filename in sorted(os.listdir(BACKUPS_DIR)):
        if not filename.startswith('state_') or not filename.endswith('.json'):
            continue
            
        filepath = os.path.join(BACKUPS_DIR, filename)
        
        # Get file stats
        stat = os.stat(filepath)
        timestamp = _parse_version_filename(filename)
        
        if timestamp:
            versions.append({
                'filename': filename,
                'timestamp': timestamp.isoformat(),
                'size': stat.st_size
            })
    
    return versions


def restore_version(filename: str) -> Optional[Dict[str, Any]]:
    """Restore state from a specific version.
    
    Args:
        filename: The backup filename to restore
        
    Returns:
        The restored state dictionary, or None if not found
    """
    filepath = os.path.join(BACKUPS_DIR, filename)
    
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r') as f:
        return json.load(f)


def get_latest_version() -> Optional[str]:
    """Get the filename of the most recent version.
    
    Returns:
        The filename of the latest backup, or None if none exist
    """
    versions = list_versions()
    
    if not versions:
        return None
    
    # Sort by timestamp and return the latest
    sorted_versions = sorted(versions, key=lambda v: v['timestamp'])
    return sorted_versions[-1]['filename']


def _parse_version_filename(filename: str) -> Optional[datetime]:
    """Parse a version filename to extract the timestamp.
    
    Args:
        filename: The filename to parse (e.g., "state_20260206_100000.json")
        
    Returns:
        datetime object, or None if parsing fails
    """
    if not filename.startswith('state_') or not filename.endswith('.json'):
        return None
    
    # Remove prefix and suffix
    middle = filename[6:-5]  # Remove "state_" prefix and ".json" suffix
    
    # Expected format: YYYYMMDD_HHMMSS
    if len(middle) != 15 or middle[8] != '_':
        return None
    
    try:
        return datetime.strptime(middle, '%Y%m%d_%H%M%S')
    except ValueError:
        return None


def delete_version(filename: str) -> bool:
    """Delete a specific version.
    
    Args:
        filename: The backup filename to delete
        
    Returns:
        True if deleted, False if not found
    """
    filepath = os.path.join(BACKUPS_DIR, filename)
    
    if not os.path.exists(filepath):
        return False
    
    os.remove(filepath)
    return True


def cleanup_old_versions(keep_count: int = 100) -> int:
    """Delete old versions, keeping the most recent ones.
    
    Args:
        keep_count: Number of versions to keep
        
    Returns:
        Number of versions deleted
    """
    versions = list_versions()
    
    if len(versions) <= keep_count:
        return 0
    
    # Sort by timestamp (oldest first)
    sorted_versions = sorted(versions, key=lambda v: v['timestamp'])
    to_delete = sorted_versions[:-keep_count]
    
    deleted = 0
    for version in to_delete:
        if delete_version(version['filename']):
            deleted += 1
    
    return deleted
