"""Tests for Memory Security Scanner - Detects sensitive data in memory files."""

import pytest
import json
import tempfile
import os
from pathlib import Path

from clawgotchi.resilience.memory_security import (
    SensitivePattern,
    SecurityLevel,
    MemorySecurityScanner,
    SecurityFinding,
    scan_memory_file,
    redact_sensitive_data
)


class TestSensitivePattern:
    """Test SensitivePattern enum and detection."""

    def test_api_key_patterns(self):
        """Detect various API key formats."""
        patterns = [
            ("sk-1234567890abcdef", True),
            ("sk_live_abc123xyz789", True),
            ("sk_test_12345", True),
            ("openai_sk_abc123", True),
            ("pk_1234567890", True),
            ("AKIAIOSFODNN7EXAMPLE", True),
            ("1234567890abcdef", False),
            ("just_a_string", False),
        ]
        for text, expected in patterns:
            result = SensitivePattern.API_KEY.matches(text)
            assert result == expected, f"Failed for {text}: expected {expected}, got {result}"

    def test_private_key_patterns(self):
        """Detect private key patterns."""
        patterns = [
            ("-----BEGIN RSA PRIVATE KEY-----", True),
            ("-----BEGIN OPENSSH PRIVATE KEY-----", True),
            ("-----BEGIN EC PRIVATE KEY-----", True),
            ("-----BEGIN PRIVATE KEY-----", True),
            ("not_a_private_key", False),
        ]
        for text, expected in patterns:
            result = SensitivePattern.PRIVATE_KEY.matches(text)
            assert result == expected, f"Failed for {text}: expected {expected}, got {result}"

    def test_database_url_patterns(self):
        """Detect database connection strings."""
        patterns = [
            ("postgresql://user:pass@localhost:5432/db", True),
            ("mysql://root:password123@localhost:3306/app", True),
            ("mongodb+srv://admin:secret123@cluster0.example.com", True),
            ("redis://:password@redis-cache:6379/0", True),
            ("sqlite:///data.db", False),
            ("just a database url", False),
        ]
        for text, expected in patterns:
            result = SensitivePattern.DATABASE_URL.matches(text)
            assert result == expected, f"Failed for {text}: expected {expected}, got {result}"

    def test_token_patterns(self):
        """Detect bearer tokens and generic tokens."""
        patterns = [
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", True),
            ("token=abc123def456", True),
            ("Authorization: Bearer xyz789", True),
            ("api_token=secret123", True),
            ("not a token at all", False),
        ]
        for text, expected in patterns:
            result = SensitivePattern.TOKEN.matches(text)
            assert result == expected, f"Failed for {text}: expected {expected}, got {result}"

    def test_email_patterns(self):
        """Detect email addresses."""
        patterns = [
            ("user@example.com", True),
            ("test.user+tag@domain.org", True),
            ("admin@company.io", True),
            ("not an email address", False),
        ]
        for text, expected in patterns:
            result = SensitivePattern.EMAIL.matches(text)
            assert result == expected, f"Failed for {text}: expected {expected}, got {result}"

    def test_ip_address_patterns(self):
        """Detect IP addresses in config strings."""
        patterns = [
            ("192.168.1.100:8080", True),
            ("10.0.0.1:22", True),
            ("Server at 192.168.1.1", True),
            ("localhost:3000", True),
            ("not an IP", False),
        ]
        for text, expected in patterns:
            result = SensitivePattern.IP_ADDRESS.matches(text)
            assert result == expected, f"Failed for {text}: expected {expected}, got {result}"


class TestSecurityLevel:
    """Test SecurityLevel enum."""

    def test_security_level_ordering(self):
        """Verify security level ordering."""
        assert SecurityLevel.CRITICAL > SecurityLevel.HIGH
        assert SecurityLevel.HIGH > SecurityLevel.MEDIUM
        assert SecurityLevel.MEDIUM > SecurityLevel.LOW
        assert SecurityLevel.LOW > SecurityLevel.INFO

    def test_security_level_from_risk_score(self):
        """Test risk score to security level conversion."""
        assert SecurityLevel.from_risk_score(95) == SecurityLevel.CRITICAL
        assert SecurityLevel.from_risk_score(75) == SecurityLevel.HIGH
        assert SecurityLevel.from_risk_score(55) == SecurityLevel.MEDIUM
        assert SecurityLevel.from_risk_score(35) == SecurityLevel.LOW
        assert SecurityLevel.from_risk_score(15) == SecurityLevel.INFO


class TestSecurityFinding:
    """Test SecurityFinding dataclass."""

    def test_finding_creation(self):
        """Create a security finding."""
        finding = SecurityFinding(
            pattern=SensitivePattern.API_KEY,
            security_level=SecurityLevel.HIGH,
            line_number=10,
            context="API key exposed in config",
            match="sk-1234567890abcdef"
        )
        assert finding.pattern == SensitivePattern.API_KEY
        assert finding.security_level == SecurityLevel.HIGH
        assert finding.line_number == 10
        assert finding.match == "sk-1234567890abcdef"


class TestMemorySecurityScanner:
    """Test MemorySecurityScanner class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory_file = Path(self.temp_dir) / "MEMORY.md"
        self.scanner = MemorySecurityScanner()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_empty_file(self):
        """Scan an empty memory file."""
        self.memory_file.write_text("")
        findings = self.scanner.scan_file(self.memory_file)
        assert len(findings) == 0

    def test_scan_no_sensitive_data(self):
        """Scan a clean memory file."""
        content = """# Today's Notes

- Had a productive session
- Built a new feature
- User seems happy
        """
        self.memory_file.write_text(content)
        findings = self.scanner.scan_file(self.memory_file)
        assert len(findings) == 0

    def test_scan_api_key_exposure(self):
        """Detect API key in memory file."""
        content = """# MEMORY.md

- Remember that the API key is sk-1234567890abcdef for future sessions
- Don't forget to use the test key sk_test_abc123 for development
        """
        self.memory_file.write_text(content)
        findings = self.scanner.scan_file(self.memory_file)
        assert len(findings) == 2
        assert findings[0].pattern == SensitivePattern.API_KEY
        assert findings[0].security_level == SecurityLevel.CRITICAL

    def test_scan_database_url(self):
        """Detect database URL in memory file."""
        content = """# Connection Notes

Database connection: postgresql://admin:secretpass@db.example.com:5432/app
        """
        self.memory_file.write_text(content)
        findings = self.scanner.scan_file(self.memory_file)
        assert len(findings) == 1
        assert findings[0].pattern == SensitivePattern.DATABASE_URL
        assert findings[0].security_level == SecurityLevel.CRITICAL

    def test_scan_multiple_issues(self):
        """Detect multiple security issues."""
        content = """# Sensitive Data Log

- OpenAI Key: sk-1234567890abcdef
- Database: mysql://root:password123@localhost:3306/production
- Token: Bearer eyJhbGciOiJIUzI1NiJ9.secret
- Admin email: admin@company.com
        """
        self.memory_file.write_text(content)
        findings = self.scanner.scan_file(self.memory_file)
        assert len(findings) >= 4

    def test_get_security_report(self):
        """Generate security report."""
        content = """# Sensitive Data

API Key: sk-test123abc
Database: postgresql://user:pass@localhost:5432/db
        """
        self.memory_file.write_text(content)
        findings = self.scanner.scan_file(self.memory_file)
        report = self.scanner.get_security_report(findings)
        
        assert "Security Scan Report" in report.summary()
        assert "Total findings:" in report.summary()

    def test_scan_respects_exclusions(self):
        """Scanner respects excluded patterns."""
        scanner = MemorySecurityScanner(exclude_patterns=[SensitivePattern.EMAIL])
        content = """# Notes

Email: admin@example.com
API Key: sk-12345
        """
        self.memory_file.write_text(content)
        findings = scanner.scan_file(self.memory_file)
        patterns_found = {f.pattern for f in findings}
        assert SensitivePattern.EMAIL not in patterns_found

    def test_scan_with_line_numbers(self):
        """Verify line numbers are accurate."""
        content = """# Line 1
This is line 2
sk-12345 on line 3
Line 4 has nothing
Token: Bearer token on line 5
"""
        self.memory_file.write_text(content)
        findings = self.scanner.scan_file(self.memory_file)
        assert len(findings) == 2
        assert findings[0].line_number == 3
        assert findings[1].line_number == 5


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_scan_memory_file_function(self):
        """Test the convenience function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("API Key: sk-1234567890\n")
            f.flush()
            
            findings = scan_memory_file(f.name)
            assert len(findings) == 1
            
            os.unlink(f.name)

    def test_redact_sensitive_data(self):
        """Test redaction of sensitive data."""
        content = "API Key: sk-1234567890abcdef, Token: secret_token"
        redacted = redact_sensitive_data(content)
        
        assert "sk-1234567890abcdef" not in redacted
        assert "secret_token" not in redacted
        assert "[REDACTED]" in redacted


class TestScannerPersistence:
    """Test scanner persistence and history."""

    def test_save_and_load_state(self):
        """Test saving and loading scanner state."""
        scanner = MemorySecurityScanner()
        
        # Add some mock findings to history
        scanner.history = [
            SecurityFinding(
                pattern=SensitivePattern.API_KEY,
                security_level=SecurityLevel.CRITICAL,
                line_number=5,
                context="Test finding",
                match="sk-test"
            )
        ]
        
        # Save state
        state_file = Path(tempfile.gettempdir()) / "test_scanner_state.json"
        scanner.save_state(state_file)
        
        # Load state
        new_scanner = MemorySecurityScanner.load_state(state_file)
        
        # Cleanup
        if state_file.exists():
            state_file.unlink()

    def test_get_statistics(self):
        """Test getting scan statistics."""
        scanner = MemorySecurityScanner()
        
        # Add mock history
        for i in range(3):
            scanner.history.append(SecurityFinding(
                pattern=SensitivePattern.API_KEY,
                security_level=SecurityLevel.CRITICAL,
                line_number=i,
                context=f"Finding {i}",
                match=f"sk-{i}"
            ))
        
        stats = scanner.get_statistics()
        assert "total_scans" in stats
        assert "critical_findings" in stats
        assert "high_findings" in stats


class TestIntegration:
    """Integration tests for the scanner."""

    def test_full_scan_workflow(self):
        """Test complete scanning workflow."""
        content = """# MEMORY.md - Session Notes

## Important Decisions
- Use API key from environment for production
- Store tokens in 1Password, never in code

## Today's Work
- Built a new feature
- Fixed bug in authentication
- Tested with the following credentials (for debugging only):
  - API Key: sk-test123abc
  - Database: postgresql://dev:devpass@localhost:5432/test_db

## Remember
- Don't commit secrets to version control
- Rotate keys every 90 days
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            
            scanner = MemorySecurityScanner()
            findings = scanner.scan_file(f.name)
            report = scanner.get_security_report(findings)
            
            # Should find the API key and database URL
            assert len(findings) >= 2
            
            # Report should mention critical issues
            assert "CRITICAL" in report.summary()
            
            # Cleanup
            os.unlink(f.name)
