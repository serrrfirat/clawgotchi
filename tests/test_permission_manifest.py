"""Tests for Permission Manifest Generator."""

import pytest
import json
import os
import time
from datetime import datetime
from unittest.mock import patch, mock_open

# Import the module under test
import sys
sys.path.insert(0, '/Users/firatsertgoz/Documents/clawgotchi')

from utils.permission_manifest import (
    PermissionManifest,
    ManifestEntry,
    PermissionType,
    generate_manifest,
    verify_manifest,
    load_manifest,
    list_manifests,
    revoke_permission,
)


class TestPermissionType:
    """Test PermissionType enum."""
    
    def test_permission_type_values(self):
        assert PermissionType.READ.value == "read"
        assert PermissionType.WRITE.value == "write"
        assert PermissionType.EXECUTE.value == "execute"
        assert PermissionType.NETWORK.value == "network"
        assert PermissionType.FILE_SYSTEM.value == "file_system"


class TestManifestEntry:
    """Test ManifestEntry dataclass."""
    
    def test_create_entry(self):
        entry = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.READ,
            resource="/path/to/resource",
            granted_at=datetime(2026, 1, 1, 12, 0, 0),
            expires_at=None,
            conditions=None,
            signature="test_signature"
        )
        assert entry.skill_name == "test_skill"
        assert entry.permission_type == PermissionType.READ
        assert entry.resource == "/path/to/resource"
        assert entry.signature == "test_signature"
    
    def test_entry_to_dict(self):
        entry = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.WRITE,
            resource="/path/to/resource",
            granted_at=datetime(2026, 1, 1, 12, 0, 0),
            expires_at=None,
            conditions={"max_size": "100MB"},
            signature="test_signature"
        )
        data = entry.to_dict()
        assert data["skill_name"] == "test_skill"
        assert data["permission_type"] == "write"
        assert data["conditions"]["max_size"] == "100MB"
    
    def test_entry_from_dict(self):
        data = {
            "skill_name": "test_skill",
            "permission_type": "read",
            "resource": "/path/to/resource",
            "granted_at": "2026-01-01T12:00:00",
            "expires_at": None,
            "conditions": None,
            "signature": "test_signature"
        }
        entry = ManifestEntry.from_dict(data)
        assert entry.skill_name == "test_skill"
        assert entry.permission_type == PermissionType.READ


class TestPermissionManifest:
    """Test PermissionManifest class."""
    
    def test_create_manifest(self):
        pm = PermissionManifest()
        assert pm.manifests == {}
        assert pm.signing_key is None
    
    def test_add_entry(self):
        pm = PermissionManifest()
        entry = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.READ,
            resource="/path/to/resource",
            granted_at=datetime.now(),
            expires_at=None,
            conditions=None,
            signature="test_signature"
        )
        pm.add_entry("test_skill", entry)
        assert "test_skill" in pm.manifests
        assert len(pm.manifests["test_skill"]) == 1
    
    def test_get_entries(self):
        pm = PermissionManifest()
        entry1 = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.READ,
            resource="/path1",
            granted_at=datetime.now(),
            expires_at=None,
            conditions=None,
            signature="sig1"
        )
        entry2 = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.WRITE,
            resource="/path2",
            granted_at=datetime.now(),
            expires_at=None,
            conditions=None,
            signature="sig2"
        )
        pm.add_entry("test_skill", entry1)
        pm.add_entry("test_skill", entry2)
        entries = pm.get_entries("test_skill")
        assert len(entries) == 2
    
    def test_revoke_permission(self):
        pm = PermissionManifest()
        entry = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.READ,
            resource="/path",
            granted_at=datetime.now(),
            expires_at=None,
            conditions=None,
            signature="sig"
        )
        pm.add_entry("test_skill", entry)
        pm.revoke_permission("test_skill", PermissionType.READ, "/path")
        entries = pm.get_entries("test_skill")
        assert len(entries) == 0
    
    def test_has_permission(self):
        pm = PermissionManifest()
        entry = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.READ,
            resource="/path",
            granted_at=datetime.now(),
            expires_at=None,
            conditions=None,
            signature="sig"
        )
        pm.add_entry("test_skill", entry)
        assert pm.has_permission("test_skill", PermissionType.READ, "/path") == True
        assert pm.has_permission("test_skill", PermissionType.WRITE, "/path") == False
    
    def test_save_and_load(self, tmp_path):
        pm = PermissionManifest()
        entry = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.READ,
            resource="/path",
            granted_at=datetime.now(),
            expires_at=None,
            conditions=None,
            signature="sig"
        )
        pm.add_entry("test_skill", entry)
        
        filepath = tmp_path / "manifest.json"
        pm.save(filepath)
        
        loaded = PermissionManifest.load(filepath)
        assert "test_skill" in loaded.manifests
        assert len(loaded.manifests["test_skill"]) == 1
    
    def test_export_audit_trail(self):
        pm = PermissionManifest()
        entry1 = ManifestEntry(
            skill_name="skill_a",
            permission_type=PermissionType.READ,
            resource="/path1",
            granted_at=datetime(2026, 1, 1, 12, 0, 0),
            expires_at=None,
            conditions=None,
            signature="sig1"
        )
        entry2 = ManifestEntry(
            skill_name="skill_b",
            permission_type=PermissionType.WRITE,
            resource="/path2",
            granted_at=datetime(2026, 1, 2, 12, 0, 0),
            expires_at=None,
            conditions=None,
            signature="sig2"
        )
        pm.add_entry("skill_a", entry1)
        pm.add_entry("skill_b", entry2)
        
        trail = pm.export_audit_trail()
        assert len(trail) == 2
        assert trail[0]["skill_name"] == "skill_a"
        assert trail[1]["skill_name"] == "skill_b"


class TestGenerateManifest:
    """Test the generate_manifest function."""
    
    def test_generate_basic_manifest(self):
        manifest = generate_manifest(
            skill_name="test_skill",
            permissions=[
                {"type": "read", "resource": "/data"},
                {"type": "write", "resource": "/output"}
            ],
            signing_key="secret_key"
        )
        assert "test_skill" in manifest.manifests
        entries = manifest.get_entries("test_skill")
        assert len(entries) == 2


class TestVerifyManifest:
    """Test the verify_manifest function."""
    
    def test_verify_valid_manifest(self, tmp_path):
        pm = PermissionManifest()
        entry = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.READ,
            resource="/path",
            granted_at=datetime.now(),
            expires_at=None,
            conditions=None,
            signature="valid_signature"
        )
        pm.add_entry("test_skill", entry)
        
        filepath = tmp_path / "manifest.json"
        pm.save(filepath)
        
        is_valid = verify_manifest(filepath)
        assert is_valid == True
    
    def test_verify_nonexistent_file(self):
        is_valid = verify_manifest("/nonexistent/manifest.json")
        assert is_valid == False


class TestListManifests:
    """Test the list_manifests function."""
    
    def test_list_from_directory(self, tmp_path):
        # Create manifest files
        (tmp_path / "manifest1.json").write_text('{"manifests": {}}')
        (tmp_path / "manifest2.json").write_text('{"manifests": {}}')
        (tmp_path / "not_a_manifest.txt").write_text("not json")
        
        manifests = list_manifests(tmp_path)
        assert len(manifests) == 2


class TestRevokePermission:
    """Test the revoke_permission function."""
    
    def test_revoke_by_skill_and_type(self):
        pm = PermissionManifest()
        entry = ManifestEntry(
            skill_name="test_skill",
            permission_type=PermissionType.READ,
            resource="/path1",
            granted_at=datetime.now(),
            expires_at=None,
            conditions=None,
            signature="sig1"
        )
        pm.add_entry("test_skill", entry)
        
        revoke_permission(pm, "test_skill", PermissionType.READ, "/path1")
        assert pm.has_permission("test_skill", PermissionType.READ, "/path1") == False


class TestManifestSurvivesRestart:
    """Test that manifests survive restarts (stored on disk)."""
    
    def test_manifest_persistence(self, tmp_path):
        # Create and save
        pm1 = PermissionManifest()
        entry = ManifestEntry(
            skill_name="persistent_skill",
            permission_type=PermissionType.NETWORK,
            resource="https://api.example.com",
            granted_at=datetime.now(),
            expires_at=None,
            conditions=None,
            signature="network_sig"
        )
        pm1.add_entry("persistent_skill", entry)
        filepath = tmp_path / "persistent_manifest.json"
        pm1.save(filepath)
        
        # Simulate restart (load fresh)
        pm2 = PermissionManifest.load(filepath)
        
        # Verify persistence
        assert pm2.has_permission(
            "persistent_skill", 
            PermissionType.NETWORK, 
            "https://api.example.com"
        ) == True
    
    def test_audit_trail_survives_restart(self, tmp_path):
        # Create with audit trail
        pm1 = PermissionManifest()
        entry = ManifestEntry(
            skill_name="audited_skill",
            permission_type=PermissionType.FILE_SYSTEM,
            resource="/etc",
            granted_at=datetime(2026, 1, 1, 12, 0, 0),
            expires_at=None,
            conditions={"read_only": True},
            signature="fs_sig"
        )
        pm1.add_entry("audited_skill", entry)
        filepath = tmp_path / "audit_manifest.json"
        pm1.save(filepath)
        
        # Load and export
        pm2 = PermissionManifest.load(filepath)
        trail = pm2.export_audit_trail()
        
        assert len(trail) == 1
        assert trail[0]["skill_name"] == "audited_skill"
        assert trail[0]["permission_type"] == "file_system"
        assert trail[0]["conditions"]["read_only"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
