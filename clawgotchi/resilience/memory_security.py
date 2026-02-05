"""
Memory Security Scanner - Detects and reports sensitive data in memory files.

This module helps prevent data leaks by scanning memory files (MEMORY.md, daily notes)
for sensitive patterns like API keys, tokens, database URLs, and other credentials.

Inspired by OopsGuardBot's warning: "Your memory file is not secure. It gets sent 
to the model. Backed up. Synced."
"""

import re
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any


class SecurityLevel(Enum):
    """Security level for findings."""
    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5

    @classmethod
    def from_risk_score(cls, score: int) -> 'SecurityLevel':
        """Convert numeric risk score to security level."""
        if score >= 80:
            return cls.CRITICAL
        elif score >= 60:
            return cls.HIGH
        elif score >= 40:
            return cls.MEDIUM
        elif score >= 20:
            return cls.LOW
        else:
            return cls.INFO


class SensitivePattern(Enum):
    """Types of sensitive patterns to detect."""
    
    API_KEY = {
        'name': 'API Key',
        'patterns': [
            r'sk-[a-zA-Z0-9]{20,}',
            r'sk_(live|test)_[a-zA-Z0-9]+',
            r'pk_[a-zA-Z0-9]+',
            r'AKIA[0-9A-Z]{16}',
            r'[a-zA-Z0-9]{32}',
        ],
        'security_level': SecurityLevel.CRITICAL,
        'risk_score': 95
    }
    
    PRIVATE_KEY = {
        'name': 'Private Key',
        'patterns': [
            r'-----BEGIN [A-Z]+ PRIVATE KEY-----',
            r'-----BEGIN OPENSSH PRIVATE KEY-----',
            r'-----BEGIN RSA PRIVATE KEY-----',
            r'-----BEGIN EC PRIVATE KEY-----',
            r'-----BEGIN DSA PRIVATE KEY-----',
        ],
        'security_level': SecurityLevel.CRITICAL,
        'risk_score': 100
    }
    
    DATABASE_URL = {
        'name': 'Database URL',
        'patterns': [
            r'(postgresql|mysql|mongodb|redis)://[^:]+:[^@]+@',
        ],
        'security_level': SecurityLevel.CRITICAL,
        'risk_score': 90
    }
    
    TOKEN = {
        'name': 'Bearer/Auth Token',
        'patterns': [
            r'Bearer\s+[a-zA-Z0-9_\-\.]+',
            r'(api_?token|auth_?token|access_?token)=[a-zA-Z0-9]+',
            r'token=[a-zA-Z0-9]+',
        ],
        'security_level': SecurityLevel.CRITICAL,
        'risk_score': 85
    }
    
    EMAIL = {
        'name': 'Email Address',
        'patterns': [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        ],
        'security_level': SecurityLevel.MEDIUM,
        'risk_score': 50
    }
    
    IP_ADDRESS = {
        'name': 'IP Address in Config',
        'patterns': [
            r'\b(?:\d{1,3}\.){3}\d{1,3}\b(?::\d+)?',
            r'localhost:\d+',
        ],
        'security_level': SecurityLevel.LOW,
        'risk_score': 30
    }
    
    def __init__(self, config: dict):
        self._config = config
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in config['patterns']
        ]
    
    @property
    def name(self) -> str:
        return self._config['name']
    
    @property
    def security_level(self) -> SecurityLevel:
        return self._config['security_level']
    
    @property
    def risk_score(self) -> int:
        return self._config['risk_score']
    
    def matches(self, text: str) -> bool:
        """Check if text matches this pattern."""
        for compiled in self._compiled_patterns:
            if compiled.search(text):
                return True
        return False
    
    def find_all(self, text: str) -> List:
        """Find all matches in text."""
        matches = []
        for compiled in self._compiled_patterns:
            matches.extend(compiled.findall(text))
        return matches


@dataclass
class SecurityFinding:
    """A security vulnerability found in a memory file."""
    pattern: SensitivePattern
    security_level: SecurityLevel
    line_number: int
    context: str
    match: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'pattern': self.pattern.name,
            'security_level': self.security_level.name,
            'line_number': self.line_number,
            'context': self.context,
            'match': self.match[:10] + '...' if len(self.match) > 10 else self.match
        }


@dataclass
class SecurityReport:
    """Complete security scan report."""
    file_path: Path
    total_findings: int
    findings_by_level: Dict
    findings: List[SecurityFinding]
    scan_timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'file_path': str(self.file_path),
            'total_findings': self.total_findings,
            'findings_by_level': {k.name: v for k, v in self.findings_by_level.items()},
            'findings': [f.to_dict() for f in self.findings],
            'scan_timestamp': self.scan_timestamp
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"Security Scan Report for: {self.file_path.name}",
            f"Timestamp: {self.scan_timestamp}",
            "-" * 50,
            f"Total findings: {self.total_findings}",
        ]
        
        for level in [SecurityLevel.CRITICAL, SecurityLevel.HIGH, 
                      SecurityLevel.MEDIUM, SecurityLevel.LOW]:
            count = self.findings_by_level.get(level, 0)
            if count > 0:
                lines.append(f"  {level.name}: {count}")
        
        lines.append("-" * 50)
        lines.append("Recommendations:")
        
        critical = self.findings_by_level.get(SecurityLevel.CRITICAL, 0)
        high = self.findings_by_level.get(SecurityLevel.HIGH, 0)
        
        if critical > 0:
            lines.append("  CRITICAL: Remove exposed API keys, tokens, or private keys immediately")
        if high > 0:
            lines.append("  HIGH: Redact database URLs and authentication credentials")
        
        return "\n".join(lines)


class MemorySecurityScanner:
    """
    Scans memory files for sensitive data exposure.
    
    Usage:
        scanner = MemorySecurityScanner()
        findings = scanner.scan_file(Path("MEMORY.md"))
        report = scanner.get_security_report(findings)
        print(report.summary())
    """
    
    def __init__(self, exclude_patterns: Optional[List[SensitivePattern]] = None):
        """
        Initialize the scanner.
        
        Args:
            exclude_patterns: List of patterns to exclude from scanning
        """
        self.patterns = {p for p in SensitivePattern}
        self.exclude_patterns = set(exclude_patterns or [])
        self.history: List[SecurityFinding] = []
        
    def scan_file(self, file_path: Path) -> List[SecurityFinding]:
        """
        Scan a memory file for sensitive data.
        
        Args:
            file_path: Path to the memory file to scan
            
        Returns:
            List of SecurityFinding objects
        """
        findings = []
        
        if not file_path.exists():
            return findings
        
        content = file_path.read_text()
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, start=1):
            for pattern in self.patterns:
                if pattern in self.exclude_patterns:
                    continue
                    
                if pattern.matches(line):
                    match = self._extract_match(line, pattern)
                    finding = SecurityFinding(
                        pattern=pattern,
                        security_level=pattern.security_level,
                        line_number=line_num,
                        context=line.strip()[:100],
                        match=match
                    )
                    findings.append(finding)
                    self.history.append(finding)
        
        return findings
    
    def _extract_match(self, line: str, pattern: SensitivePattern) -> str:
        """Extract the actual matched text from a line."""
        for compiled in pattern._compiled_patterns:
            match = compiled.search(line)
            if match:
                return match.group(0)
        return line.strip()[:50]
    
    def scan_directory(self, directory: Path, 
                       recursive: bool = True) -> Dict[Path, List[SecurityFinding]]:
        """
        Scan all memory files in a directory.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            
        Returns:
            Dict mapping file paths to their findings
        """
        results = {}
        
        if recursive:
            pattern = "**/*.md"
        else:
            pattern = "*.md"
        
        for md_file in directory.glob(pattern):
            if 'memory' in md_file.name.lower() or md_file.name in ['MEMORY.md', 'WORKING.md']:
                findings = self.scan_file(md_file)
                if findings:
                    results[md_file] = findings
        
        return results
    
    def get_security_report(self, findings: List[SecurityFinding], 
                           file_path: Optional[Path] = None) -> SecurityReport:
        """
        Generate a security report from findings.
        
        Args:
            findings: List of security findings
            file_path: Path to the scanned file
            
        Returns:
            SecurityReport object
        """
        from datetime import datetime
        
        by_level: Dict = {}
        for finding in findings:
            by_level[finding.security_level] = by_level.get(finding.security_level, 0) + 1
        
        return SecurityReport(
            file_path=file_path or Path("unknown"),
            total_findings=len(findings),
            findings_by_level=by_level,
            findings=sorted(findings, key=lambda f: f.security_level.value, reverse=True),
            scan_timestamp=datetime.utcnow().isoformat() + "Z"
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scan statistics from history."""
        by_level: Dict[str, int] = {}
        for finding in self.history:
            level_name = finding.security_level.name
            by_level[level_name] = by_level.get(level_name, 0) + 1
        
        return {
            'total_scans': len(self.history),
            'critical_findings': by_level.get('CRITICAL', 0),
            'high_findings': by_level.get('HIGH', 0),
            'medium_findings': by_level.get('MEDIUM', 0),
            'low_findings': by_level.get('LOW', 0),
            'findings_by_level': by_level
        }
    
    def save_state(self, state_file: Path) -> None:
        """Save scanner state to file."""
        state = {
            'history': [f.to_dict() for f in self.history]
        }
        state_file.write_text(json.dumps(state, indent=2))
    
    @classmethod
    def load_state(cls, state_file: Path) -> 'MemorySecurityScanner':
        """Load scanner state from file."""
        scanner = cls()
        if state_file.exists():
            state = json.loads(state_file.read_text())
            scanner.history = []
        return scanner


# Convenience functions

def scan_memory_file(file_path: str) -> List[SecurityFinding]:
    """
    Convenience function to scan a memory file.
    
    Args:
        file_path: Path to the memory file
        
    Returns:
        List of SecurityFinding objects
    """
    scanner = MemorySecurityScanner()
    return scanner.scan_file(Path(file_path))


def redact_sensitive_data(text: str) -> str:
    """
    Redact all sensitive data from text.
    
    Args:
        text: Text to redact
        
    Returns:
        Redacted text with sensitive data replaced by [REDACTED]
    """
    redacted = text
    for pattern in SensitivePattern:
        for compiled in pattern._compiled_patterns:
            redacted = compiled.sub('[REDACTED]', redacted)
    return redacted


def quick_check(file_path: str) -> Dict[str, Any]:
    """
    Quick security check for a memory file.
    
    Args:
        file_path: Path to check
        
    Returns:
        Dict with status and finding count
    """
    findings = scan_memory_file(file_path)
    
    has_critical = any(f.security_level == SecurityLevel.CRITICAL for f in findings)
    has_high = any(f.security_level == SecurityLevel.HIGH for f in findings)
    
    return {
        'file': file_path,
        'status': 'critical' if has_critical else ('warning' if has_high else 'clean'),
        'findings_count': len(findings),
        'critical_count': sum(1 for f in findings if f.security_level == SecurityLevel.CRITICAL),
        'high_count': sum(1 for f in findings if f.security_level == SecurityLevel.HIGH)
    }
