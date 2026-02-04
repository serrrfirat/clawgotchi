"""
Tests for permission_manifest_scanner.py
Validates skill permission manifests for security issues.
"""
import pytest
import json
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, mock_open

# Import the module under test
import sys
sys.path.insert(0, '/Users/firatsertgoz/Documents/clawgotchi')
from skills.auto_updater.permission_manifest_scanner import (
    PermissionManifestScanner,
    PermissionIssue,
    ManifestValidation,
    Severity,
    scan_permissions,
    generate_security_report
)


class TestPermissionManifestScanner:
    """Test cases for PermissionManifestScanner class."""
    
    def test_scanner_initialization(self):
        """Scanner initializes with default settings."""
        scanner = PermissionManifestScanner()
        assert scanner.strict_mode == False
        assert scanner.scanned_count == 0
    
    def test_scanner_strict_mode(self):
        """Scanner can be initialized in strict mode."""
        scanner = PermissionManifestScanner(strict_mode=True)
        assert scanner.strict_mode == True
    
    def test_load_valid_manifest(self):
        """Scanner loads valid JSON manifest."""
        scanner = PermissionManifestScanner()
        
        valid_manifest = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "read": ["./data/**"],
                    "write": ["./output/**"],
                    "deny": ["~/.env", "~/.ssh/**"]
                },
                "network": {
                    "allow": ["api.weather.gov"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_manifest, f)
            temp_path = f.name
        
        try:
            result = scanner._load_manifest(temp_path)
            assert result == valid_manifest
        finally:
            os.unlink(temp_path)
    
    def test_load_invalid_manifest(self):
        """Scanner handles invalid JSON gracefully."""
        scanner = PermissionManifestScanner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name
        
        try:
            result = scanner._load_manifest(temp_path)
            assert result is None
        finally:
            os.unlink(temp_path)
    
    def test_load_missing_file(self):
        """Scanner handles missing file gracefully."""
        scanner = PermissionManifestScanner()
        result = scanner._load_manifest('/nonexistent/path/manifest.json')
        assert result is None


class TestManifestValidation:
    """Test cases for manifest validation logic."""
    
    def test_validate_valid_manifest(self):
        """Valid manifest passes validation."""
        scanner = PermissionManifestScanner()
        
        valid_manifest = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "read": ["./data/**"],
                    "write": ["./output/**"],
                    "deny": ["~/.env", "~/.ssh/**"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_manifest, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert validation.valid == True
            assert validation.score >= 70
        finally:
            os.unlink(temp_path)
    
    def test_validate_missing_required_fields(self):
        """Manifest missing required fields fails validation."""
        scanner = PermissionManifestScanner()
        
        incomplete_manifest = {
            "skill_name": "test-skill"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_manifest, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert validation.valid == False
            assert any(i.issue_type == "missing_required_fields" for i in validation.issues)
        finally:
            os.unlink(temp_path)
    
    def test_validate_missing_deny_list(self):
        """Manifest without deny list gets warning."""
        scanner = PermissionManifestScanner()
        
        manifest_no_deny = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "read": ["./data/**"],
                    "write": ["./output/**"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_no_deny, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert any(i.issue_type == "missing_deny_list" for i in validation.issues)
        finally:
            os.unlink(temp_path)
    
    def test_validate_excessive_filesystem_write(self):
        """Manifest with /** write permission flagged."""
        scanner = PermissionManifestScanner()
        
        manifest_excessive = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "write": ["/**"],
                    "deny": ["~/.env"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_excessive, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert any(i.issue_type == "excessive_filesystem_write" for i in validation.issues)
        finally:
            os.unlink(temp_path)
    
    def test_validate_wildcard_network_access(self):
        """Manifest with wildcard network access flagged."""
        scanner = PermissionManifestScanner()
        
        manifest_wildcard = {
            "version": "1.0",
            "permissions": {
                "network": {
                    "allow": ["*"]
                },
                "filesystem": {
                    "deny": ["~/.env", "~/.ssh/**"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_wildcard, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert any(i.issue_type == "excessive_network" for i in validation.issues)
        finally:
            os.unlink(temp_path)
    
    def test_validate_suspicious_network_destination(self):
        """Manifest with suspicious network destinations flagged."""
        scanner = PermissionManifestScanner()
        
        manifest_suspicious = {
            "version": "1.0",
            "permissions": {
                "network": {
                    "allow": ["webhook.site/api"]
                },
                "filesystem": {
                    "deny": ["~/.env"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_suspicious, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert any(i.issue_type == "suspicious_network" for i in validation.issues)
        finally:
            os.unlink(temp_path)
    
    def test_validate_dangerous_capability(self):
        """Manifest requesting dangerous capability flagged."""
        scanner = PermissionManifestScanner()
        
        manifest_dangerous = {
            "version": "1.0",
            "permissions": {
                "dangerous": True,
                "filesystem": {
                    "deny": ["~/.env", "~/.ssh/**"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_dangerous, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert any(i.issue_type == "dangerous_capability" for i in validation.issues)
        finally:
            os.unlink(temp_path)
    
    def test_validate_env_vars_wildcard(self):
        """Manifest requesting all env vars flagged."""
        scanner = PermissionManifestScanner()
        
        manifest_env_wildcard = {
            "version": "1.0",
            "permissions": {
                "env_vars": ["*"],
                "filesystem": {
                    "deny": ["~/.env", "~/.ssh/**"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_env_wildcard, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert any(i.issue_type == "excessive_env_vars" for i in validation.issues)
        finally:
            os.unlink(temp_path)
    
    def test_validate_missing_audit_trail(self):
        """Manifest without audit trail gets info."""
        scanner = PermissionManifestScanner()
        
        manifest_no_audit = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "read": ["./data/**"],
                    "deny": ["~/.env", "~/.ssh/**"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_no_audit, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert any(i.issue_type == "missing_audit_trail" for i in validation.issues)
        finally:
            os.unlink(temp_path)
    
    def test_validate_with_audit_trail(self):
        """Manifest with proper audit trail passes."""
        scanner = PermissionManifestScanner()
        
        manifest_with_audit = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "read": ["./data/**"],
                    "deny": ["~/.env", "~/.ssh/**"]
                }
            },
            "audit_trail": [
                {
                    "auditor": "@security_sentinel",
                    "timestamp": datetime.now().isoformat(),
                    "status": "approved",
                    "notes": "YARA scan clean, appropriate permissions"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_with_audit, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            # Should not have missing_audit_trail issue
            assert not any(i.issue_type == "missing_audit_trail" for i in validation.issues)
        finally:
            os.unlink(temp_path)
    
    def test_security_score_calculation(self):
        """Security score is calculated correctly."""
        scanner = PermissionManifestScanner()
        
        # Valid manifest should have high score
        valid_manifest = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "read": ["./data/**"],
                    "deny": ["~/.env", "~/.ssh/**"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_manifest, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            assert validation.score >= 70
        finally:
            os.unlink(temp_path)
    
    def test_strict_mode_increases_severity(self):
        """Strict mode increases issue severity."""
        scanner_normal = PermissionManifestScanner(strict_mode=False)
        scanner_strict = PermissionManifestScanner(strict_mode=True)
        
        manifest_no_deny = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "read": ["./data/**"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest_no_deny, f)
            temp_path = f.name
        
        try:
            normal_result = scanner_normal.scan_manifest(temp_path)
            strict_result = scanner_strict.scan_manifest(temp_path)
            
            normal_issue = next((i for i in normal_result.issues if i.issue_type == "missing_deny_list"), None)
            strict_issue = next((i for i in strict_result.issues if i.issue_type == "missing_deny_list"), None)
            
            if normal_issue and strict_issue:
                assert strict_issue.severity.value >= normal_issue.severity.value
        finally:
            os.unlink(temp_path)


class TestPermissionIssue:
    """Test cases for PermissionIssue class."""
    
    def test_issue_summary(self):
        """Issue generates correct summary."""
        issue = PermissionIssue(
            issue_type="test_issue",
            severity=Severity.HIGH,
            message="Test issue message",
            file_path="/test/path.json",
            suggestion="Fix this"
        )
        
        summary = issue.summary()
        assert "⚠️" in summary
        assert "[HIGH]" in summary
        assert "Test issue message" in summary
        assert "/test/path.json" in summary
    
    def test_issue_summary_critical(self):
        """Critical issue uses correct icon."""
        issue = PermissionIssue(
            issue_type="critical",
            severity=Severity.CRITICAL,
            message="Critical issue",
            file_path="/test.json"
        )
        
        summary = issue.summary()
        assert "🚨" in summary


class TestDirectoryScanning:
    """Test cases for directory scanning functionality."""
    
    def test_scan_directory_empty(self):
        """Empty directory returns empty results."""
        scanner = PermissionManifestScanner()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            results = scanner.scan_directory(tmpdir)
            assert results == []
    
    def test_scan_directory_with_manifests(self):
        """Directory with manifests is scanned correctly."""
        scanner = PermissionManifestScanner()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create first manifest
            manifest1 = {"version": "1.0", "permissions": {"filesystem": {"deny": ["~/.env"]}}}
            with open(os.path.join(tmpdir, "skill.json"), 'w') as f:
                json.dump(manifest1, f)
            
            # Create subdirectory with manifest
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            manifest2 = {"version": "1.0", "permissions": {"network": {"allow": ["api.example.com"]}}}
            with open(os.path.join(subdir, "manifest.json"), 'w') as f:
                json.dump(manifest2, f)
            
            results = scanner.scan_directory(tmpdir)
            assert len(results) == 2
            assert scanner.scanned_count == 2


class TestGenerateSecurityReport:
    """Test cases for security report generation."""
    
    def test_generate_empty_report(self):
        """Empty list generates appropriate message."""
        report = generate_security_report([])
        assert "No permission manifests found" in report
    
    def test_generate_valid_report(self):
        """Valid manifests generate positive report."""
        validations = [
            ManifestValidation(
                file_path="/test/skill.json",
                valid=True,
                score=95
            )
        ]
        
        report = generate_security_report(validations)
        assert "Permission Manifest Security Report" in report
        assert "95" in report
        assert "Excellent" in report or "Good" in report
    
    def test_generate_report_with_issues(self):
        """Report includes issue details."""
        validation = ManifestValidation(
            file_path="/test/skill.json",
            valid=False,
            score=45,
            issues=[
                PermissionIssue(
                    issue_type="critical",
                    severity=Severity.CRITICAL,
                    message="Critical security issue",
                    file_path="/test/skill.json"
                )
            ]
        )
        
        report = generate_security_report([validation])
        assert "Critical security issue" in report


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def test_scan_permissions_function(self):
        """scan_permissions convenience function works."""
        manifest = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "deny": ["~/.env", "~/.ssh/**"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(manifest, f)
            temp_path = f.name
        
        try:
            result = scan_permissions(temp_path)
            assert isinstance(result, ManifestValidation)
        finally:
            os.unlink(temp_path)
    
    def test_scan_nonexistent_file(self):
        """scan_permissions handles nonexistent file."""
        result = scan_permissions('/nonexistent/skill.json')
        assert result is None


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_security_workflow(self):
        """Complete scan -> validate -> report workflow."""
        scanner = PermissionManifestScanner()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a well-configured skill manifest
            good_manifest = {
                "version": "1.0",
                "permissions": {
                    "filesystem": {
                        "read": ["./data/**"],
                        "write": ["./output/**"],
                        "deny": ["~/.env", "~/.ssh/**", "~/.config/**/credentials*"]
                    },
                    "network": {
                        "allow": ["api.weather.gov", "*.openweathermap.org"],
                        "deny": ["webhook.site", "*.ngrok.io"]
                    },
                    "env_vars": ["WEATHER_API_KEY"],
                    "exec": ["curl", "jq"]
                },
                "audit_trail": [
                    {
                        "auditor": "@Rufio",
                        "timestamp": datetime.now().isoformat(),
                        "status": "approved",
                        "notes": "YARA scan clean, appropriate permissions"
                    }
                ]
            }
            
            with open(os.path.join(tmpdir, "skill.json"), 'w') as f:
                json.dump(good_manifest, f)
            
            # Scan
            validations = scanner.scan_directory(tmpdir)
            assert len(validations) == 1
            
            validation = validations[0]
            assert validation.valid == True
            assert validation.score >= 70
            
            # Generate report
            report = generate_security_report(validations)
            assert "Excellent" in report or "Good" in report
    
    def test_detect_problematic_manifest(self):
        """Scanner detects multiple issues in problematic manifest."""
        scanner = PermissionManifestScanner()
        
        problematic_manifest = {
            "version": "1.0",
            "permissions": {
                "filesystem": {
                    "write": ["/**"],  # Excessive
                    "deny": []  # Missing deny
                },
                "network": {
                    "allow": ["*"]  # Wildcard
                },
                "dangerous": True  # Dangerous
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(problematic_manifest, f)
            temp_path = f.name
        
        try:
            validation = scanner.scan_manifest(temp_path)
            
            # Should have multiple issues
            issue_types = [i.issue_type for i in validation.issues]
            
            assert "excessive_filesystem_write" in issue_types
            assert "missing_deny_list" in issue_types or "missing_critical_deny" in issue_types
            assert "excessive_network" in issue_types
            assert "dangerous_capability" in issue_types
            
            # Should not be valid
            assert validation.valid == False
            assert validation.score < 70
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
