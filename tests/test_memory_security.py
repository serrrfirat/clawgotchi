"""Tests for Memory Security Scanner."""

import pytest
import tempfile
import os
from pathlib import Path
from memory_security import MemorySecurityScanner, SecurityFinding


@pytest.fixture
def temp_memory_dir():
    """Create a temporary memory directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def scanner(temp_memory_dir):
    """Create a scanner with temp directory."""
    return MemorySecurityScanner(memory_dir=temp_memory_dir)


class TestSecretPatternDetection:
    """Test detection of various secret patterns."""
    
    def test_detects_api_key(self, scanner, temp_memory_dir):
        """Should detect API keys in text files."""
        test_file = Path(temp_memory_dir) / "test.md"
        test_file.write_text('api_key = "sk_test_12345678901234567890123456"')
        
        findings = scanner.scan_file(test_file)
        
        assert len(findings) >= 1
        api_findings = [f for f in findings if f.finding_type == 'API Key']
        assert len(api_findings) == 1
    
    def test_detects_github_token(self, scanner, temp_memory_dir):
        """Should detect GitHub tokens."""
        test_file = Path(temp_memory_dir) / "config.txt"
        test_file.write_text('ghp_abcdefghijklmnopqrstuvwxyz1234567890')
        
        findings = scanner.scan_file(test_file)
        
        gh_findings = [f for f in findings if f.finding_type == 'GitHub Token']
        assert len(gh_findings) == 1
        assert gh_findings[0].severity == 'high'
    
    def test_detects_moltbook_key(self, scanner, temp_memory_dir):
        """Should detect Moltbook API keys."""
        test_file = Path(temp_memory_dir) / ".moltbook.json"
        test_file.write_text('{"api_key": "moltbook_sk_Cqk7cihbVaCVqRklCr4OHb2iXeOw645H"}')
        
        findings = scanner.scan_file(test_file)
        
        molt_findings = [f for f in findings if f.finding_type == 'Moltbook API Key']
        assert len(molt_findings) == 1
    
    def test_detects_private_key_header(self, scanner, temp_memory_dir):
        """Should detect private key headers."""
        test_file = Path(temp_memory_dir) / "key.txt"
        test_file.write_text('-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----')
        
        findings = scanner.scan_file(test_file)
        
        key_findings = [f for f in findings if f.finding_type == 'Private Key']
        assert len(key_findings) == 1
        assert key_findings[0].severity == 'high'
    
    def test_detects_email_address(self, scanner, temp_memory_dir):
        """Should detect email addresses as PII."""
        test_file = Path(temp_memory_dir) / "contacts.md"
        test_file.write_text('Contact: firat@example.com for questions')
        
        findings = scanner.scan_file(test_file)
        
        email_findings = [f for f in findings if f.finding_type == 'Email Address']
        assert len(email_findings) == 1
        assert email_findings[0].severity == 'medium'
    
    def test_detects_password(self, scanner, temp_memory_dir):
        """Should detect passwords."""
        test_file = Path(temp_memory_dir) / "secrets.txt"
        test_file.write_text('password = "supersecret123"')
        
        findings = scanner.scan_file(test_file)
        
        pwd_findings = [f for f in findings if f.finding_type == 'Password']
        assert len(pwd_findings) == 1
    
    def test_detects_internal_ip(self, scanner, temp_memory_dir):
        """Should detect internal IP addresses."""
        test_file = Path(temp_memory_dir) / "network.md"
        test_file.write_text('Server at 192.168.1.100 running the service')
        
        findings = scanner.scan_file(test_file)
        
        ip_findings = [f for f in findings if f.finding_type == 'Internal IP']
        assert len(ip_findings) == 1
    
    def test_detects_user_home_path(self, scanner, temp_memory_dir):
        """Should detect user home paths."""
        test_file = Path(temp_memory_dir) / "paths.md"
        test_file.write_text('Working in /Users/firatsertgoz/Documents/clawgotchi')
        
        findings = scanner.scan_file(test_file)
        
        path_findings = [f for f in findings if f.finding_type == 'User Home Path']
        assert len(path_findings) == 1


class TestJSONFileScanning:
    """Test scanning of JSON files."""
    
    def test_scans_json_object(self, scanner, temp_memory_dir):
        """Should scan JSON objects for secrets."""
        test_file = Path(temp_memory_dir) / "config.json"
        test_file.write_text('{"api_key": "sk_live_12345", "name": "test"}')
        
        findings = scanner.scan_file(test_file)
        
        assert len(findings) >= 1
    
    def test_scans_jsonl(self, scanner, temp_memory_dir):
        """Should scan JSONL files line by line."""
        test_file = Path(temp_memory_dir) / "rejections.jsonl"
        # Use two API keys to ensure multi-line detection
        test_file.write_text('{"subject": "test", "api_key": "sk_test_123"}\n{"subject": "test2", "api_key": "sk_prod_456"}')
        
        findings = scanner.scan_file(test_file)
        
        assert len(findings) >= 2


class TestScannerBehavior:
    """Test general scanner behavior."""
    
    def test_empty_file_returns_no_findings(self, scanner, temp_memory_dir):
        """Empty files should return no findings."""
        test_file = Path(temp_memory_dir) / "empty.txt"
        test_file.write_text('')
        
        findings = scanner.scan_file(test_file)
        
        assert len(findings) == 0
    
    def test_nonexistent_file_returns_empty(self, scanner):
        """Nonexistent files should return empty list."""
        findings = scanner.scan_file(Path('/nonexistent/file.txt'))
        
        assert len(findings) == 0
    
    def test_scan_all_with_no_files(self, scanner):
        """Scanning empty directory should work."""
        result = scanner.scan_all()
        
        assert result['scanned_files'] == 0
        assert len(result['findings']) == 0
    
    def test_scan_all_finds_multiple_files(self, scanner, temp_memory_dir):
        """Should scan multiple files in directory."""
        # Create multiple test files
        (Path(temp_memory_dir) / "file1.txt").write_text('api_key = "sk_test_1"')
        (Path(temp_memory_dir) / "file2.txt").write_text('api_key = "sk_test_2"')
        (Path(temp_memory_dir) / "subdir").mkdir()
        (Path(temp_memory_dir) / "subdir" / "file3.txt").write_text('api_key = "sk_test_3"')
        
        result = scanner.scan_all()
        
        assert result['scanned_files'] >= 4
        # Should find at least 3 API keys
        api_findings = [f for f in result['findings'] if f['finding_type'] == 'API Key']
        assert len(api_findings) >= 3
    
    def test_severity_counts(self, scanner, temp_memory_dir):
        """Should correctly count findings by severity."""
        # Create files with different secret types
        # GitHub token requires 36+ chars
        (Path(temp_memory_dir) / "high.txt").write_text('ghp_abcdefghijklmnopqrstuvwxyz1234567890ab')  # High severity
        (Path(temp_memory_dir) / "low.txt").write_text('192.168.1.1')  # Low severity
        
        result = scanner.scan_all()
        
        assert result['severity_counts']['high'] >= 1
        assert result['severity_counts']['low'] >= 1


class TestSecurityFinding:
    """Test SecurityFinding dataclass."""
    
    def test_finding_has_required_fields(self):
        """SecurityFinding should have all required fields."""
        finding = SecurityFinding(
            file_path="/test/file.txt",
            line_number=10,
            finding_type="API Key",
            severity="high",
            snippet="api_key = 'sk_test_123'",
            recommendation="Remove this key"
        )
        
        assert finding.file_path == "/test/file.txt"
        assert finding.line_number == 10
        assert finding.finding_type == "API Key"
        assert finding.severity == "high"
        assert finding.snippet == "api_key = 'sk_test_123'"
        assert finding.recommendation == "Remove this key"
    
    def test_finding_dict_conversion(self):
        """Should convert to dict for JSON serialization."""
        finding = SecurityFinding(
            file_path="/test/file.txt",
            line_number=10,
            finding_type="API Key",
            severity="high",
            snippet="test",
            recommendation="Remove this key"
        )
        
        finding_dict = finding.__dict__
        
        assert 'file_path' in finding_dict
        assert 'severity' in finding_dict
        assert finding_dict['severity'] == 'high'
