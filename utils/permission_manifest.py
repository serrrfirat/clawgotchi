"""
Permission Manifest Generator

Generates signed, auditable permission manifests for autonomous agents.
Inspired by BadPinkman's post on earned autonomy:
"signed skills, permission manifests, and an audit trail that survives a restart"

Features:
- Define permission boundaries for skills
- Sign manifests with timestamps
- Store manifests persistently (survives restarts)
- Verify permission grants at runtime
- Export audit trails
"""

import json
import hashlib
import hmac
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum


class PermissionType(Enum):
    """Types of permissions an agent skill can request."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"


@dataclass
class ManifestEntry:
    """
    A single permission entry in a manifest.
    
    Attributes:
        skill_name: Name of the skill requesting permission
        permission_type: Type of permission (read, write, execute, etc.)
        resource: The resource this permission applies to
        granted_at: When permission was granted
        expires_at: Optional expiration timestamp
        conditions: Optional conditions on the permission
        signature: Cryptographic signature of this entry
    """
    skill_name: str
    permission_type: PermissionType
    resource: str
    granted_at: datetime
    expires_at: Optional[datetime] = None
    conditions: Optional[Dict[str, Any]] = None
    signature: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for serialization."""
        return {
            "skill_name": self.skill_name,
            "permission_type": self.permission_type.value,
            "resource": self.resource,
            "granted_at": self.granted_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "conditions": self.conditions,
            "signature": self.signature
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManifestEntry":
        """Create entry from dictionary."""
        return cls(
            skill_name=data["skill_name"],
            permission_type=PermissionType(data["permission_type"]),
            resource=data["resource"],
            granted_at=datetime.fromisoformat(data["granted_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            conditions=data.get("conditions"),
            signature=data.get("signature", "")
        )
    
    def is_expired(self) -> bool:
        """Check if this permission has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class PermissionManifest:
    """
    A collection of permission manifests for an agent.
    
    This is the core class for managing permission boundaries.
    Manifests are stored on disk to survive restarts.
    """
    manifests: Dict[str, List[ManifestEntry]] = field(default_factory=dict)
    signing_key: Optional[str] = None
    
    def add_entry(self, skill_name: str, entry: ManifestEntry) -> None:
        """Add a permission entry for a skill."""
        if skill_name not in self.manifests:
            self.manifests[skill_name] = []
        self.manifests[skill_name].append(entry)
    
    def get_entries(self, skill_name: str) -> List[ManifestEntry]:
        """Get all permission entries for a skill."""
        return self.manifests.get(skill_name, [])
    
    def has_permission(
        self, 
        skill_name: str, 
        permission_type: PermissionType, 
        resource: str
    ) -> bool:
        """
        Check if a skill has a specific permission.
        
        Args:
            skill_name: Name of the skill
            permission_type: Type of permission to check
            resource: Resource to check access for
            
        Returns:
            True if permission is granted and not expired
        """
        entries = self.get_entries(skill_name)
        for entry in entries:
            if (entry.permission_type == permission_type and 
                entry.resource == resource and 
                not entry.is_expired()):
                return True
        return False
    
    def get_permissions_for_skill(self, skill_name: str) -> List[Dict[str, Any]]:
        """Get all active permissions for a skill as dictionaries."""
        entries = self.get_entries(skill_name)
        return [
            entry.to_dict() 
            for entry in entries 
            if not entry.is_expired()
        ]
    
    def revoke_permission(
        self, 
        skill_name: str, 
        permission_type: PermissionType, 
        resource: str
    ) -> bool:
        """
        Revoke a specific permission from a skill.
        
        Returns:
            True if permission was found and revoked
        """
        if skill_name not in self.manifests:
            return False
        
        original_count = len(self.manifests[skill_name])
        self.manifests[skill_name] = [
            entry 
            for entry in self.manifests[skill_name]
            if not (entry.permission_type == permission_type and 
                    entry.resource == resource)
        ]
        return len(self.manifests[skill_name]) < original_count
    
    def save(self, filepath: str) -> None:
        """Save manifest to disk as JSON."""
        data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "manifests": {
                skill_name: [entry.to_dict() for entry in entries]
                for skill_name, entries in self.manifests.items()
            }
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> "PermissionManifest":
        """Load manifest from disk."""
        if not os.path.exists(filepath):
            return cls()
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        pm = cls()
        for skill_name, entries_data in data.get("manifests", {}).items():
            for entry_data in entries_data:
                entry = ManifestEntry.from_dict(entry_data)
                pm.manifests[skill_name] = pm.manifests.get(skill_name, [])
                pm.manifests[skill_name].append(entry)
        
        return pm
    
    def export_audit_trail(self) -> List[Dict[str, Any]]:
        """
        Export all permission grants as an audit trail.
        Useful for compliance and debugging.
        """
        trail = []
        for skill_name, entries in self.manifests.items():
            for entry in entries:
                trail.append({
                    "skill_name": skill_name,
                    "permission_type": entry.permission_type.value,
                    "resource": entry.resource,
                    "granted_at": entry.granted_at.isoformat(),
                    "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                    "conditions": entry.conditions,
                    "status": "active" if not entry.is_expired() else "expired"
                })
        return sorted(trail, key=lambda x: x["granted_at"])
    
    def cleanup_expired(self) -> int:
        """Remove expired permissions. Returns count of removed entries."""
        count = 0
        for skill_name in list(self.manifests.keys()):
            original = len(self.manifests[skill_name])
            self.manifests[skill_name] = [
                entry 
                for entry in self.manifests[skill_name]
                if not entry.is_expired()
            ]
            count += original - len(self.manifests[skill_name])
        return count
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all permissions."""
        active = 0
        expired = 0
        by_type = {}
        
        for entries in self.manifests.values():
            for entry in entries:
                if entry.is_expired():
                    expired += 1
                else:
                    active += 1
                ptype = entry.permission_type.value
                by_type[ptype] = by_type.get(ptype, 0) + 1
        
        return {
            "skills_with_permissions": len(self.manifests),
            "active_permissions": active,
            "expired_permissions": expired,
            "by_type": by_type
        }


def _sign_entry(entry: ManifestEntry, key: str) -> str:
    """Create HMAC signature for an entry."""
    data = f"{entry.skill_name}:{entry.permission_type.value}:{entry.resource}:{entry.granted_at.isoformat()}"
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()


def generate_manifest(
    skill_name: str,
    permissions: List[Dict[str, Any]],
    signing_key: Optional[str] = None,
    expires_in_days: Optional[int] = None
) -> PermissionManifest:
    """
    Generate a permission manifest for a skill.
    
    Args:
        skill_name: Name of the skill
        permissions: List of permission dicts with 'type' and 'resource'
        signing_key: Optional key for signing entries
        expires_in_days: Optional expiration for all permissions
        
    Returns:
        PermissionManifest with entries added
    """
    manifest = PermissionManifest(signing_key=signing_key)
    
    for perm in permissions:
        ptype = PermissionType(perm["type"])
        resource = perm["resource"]
        conditions = perm.get("conditions")
        
        granted_at = datetime.now()
        expires_at = None
        if expires_in_days:
            from datetime import timedelta
            expires_at = granted_at + timedelta(days=expires_in_days)
        
        entry = ManifestEntry(
            skill_name=skill_name,
            permission_type=ptype,
            resource=resource,
            granted_at=granted_at,
            expires_at=expires_at,
            conditions=conditions,
            signature=""
        )
        
        # Sign if key provided
        if signing_key:
            entry.signature = _sign_entry(entry, signing_key)
        
        manifest.add_entry(skill_name, entry)
    
    return manifest


def verify_manifest(filepath: str) -> bool:
    """
    Verify a manifest file exists and is valid JSON.
    
    Args:
        filepath: Path to manifest file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        # Basic validation
        assert "manifests" in data
        return True
    except (json.JSONDecodeError, FileNotFoundError, AssertionError):
        return False


def load_manifest(filepath: str) -> PermissionManifest:
    """Load a permission manifest from disk."""
    return PermissionManifest.load(filepath)


def list_manifests(directory: str) -> List[str]:
    """
    List all manifest files in a directory.
    
    Args:
        directory: Directory to search
        
    Returns:
        List of .json manifest file paths
    """
    manifests = []
    if not os.path.exists(directory):
        return manifests
    
    for f in os.listdir(directory):
        if f.endswith(".json"):
            filepath = os.path.join(directory, f)
            if verify_manifest(filepath):
                manifests.append(filepath)
    
    return manifests


def revoke_permission(
    manifest: PermissionManifest,
    skill_name: str,
    permission_type: PermissionType,
    resource: str
) -> bool:
    """Convenience function to revoke a permission."""
    return manifest.revoke_permission(skill_name, permission_type, resource)


def check_permission(
    manifest: PermissionManifest,
    skill_name: str,
    permission_type: str,
    resource: str
) -> bool:
    """
    Check if a skill has a specific permission.
    
    Args:
        manifest: PermissionManifest to check
        skill_name: Name of the skill
        permission_type: Type of permission as string
        resource: Resource to check
        
    Returns:
        True if permission is granted
    """
    try:
        ptype = PermissionType(permission_type)
    except ValueError:
        return False
    return manifest.has_permission(skill_name, ptype, resource)
