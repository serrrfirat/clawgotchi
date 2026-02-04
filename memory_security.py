"""
Memory Security Scanner - Detects secrets and sensitive data in agent memory.

Inspired by kuro_noir's post: "Memory is an attack surface"
- Agents store context in markdown, sqlite, vector dbs
- Often unencrypted and world-readable
- Your memory contains API keys, system paths, user habits, security gaps

This scanner helps identify what secrets might be leaking through memory.
"""

import re
import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SecurityFinding:
    """A potential security issue found in memory."""
    file_path: str
    line_number: int
    finding_type: str
    severity: str  # high, medium, low
    snippet: str
    recommendation: str


# Common secret patterns to detect
SECRET_PATTERNS = [
    # API Keys and Tokens - handles both JSON (quoted keys) and text (unquoted)
    (r'(?i)"?api[_-]?key"?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{8,})', 'API Key', 'high'),
    (r'(?i)sk[-_][a-zA-Z0-9]{8,}', 'Secret Key', 'high'),
    (r'(?i)(Bearer|token|auth)[_\s]*[:=][""]?\s*[A-Za-z0-9\-\._~\+\/]+={0,2}', 'Auth Token', 'high'),
    (r'(?i)ghp_[a-zA-Z0-9]{36,}', 'GitHub Token', 'high'),
    (r'(?i)moltbook[_-]?sk_[a-zA-Z0-9]{8,}', 'Moltbook API Key', 'high'),
    
    # Passwords
    (r'(?i)(password|pwd|passwd)[_\s]*[=:]["\s]*([^\s"\'\]>]+)', 'Password', 'high'),
    (r'["\']password["\']?\s*:\s*["\'][^"\']+["\']', 'Password', 'high'),
    
    # Database Connections
    (r'(?i)(mongodb|postgres|mysql|redis)[^\s]*connection[^\s]*[=:]["\s]*[a-zA-Z0-9\-\._~\+\/]+', 'Database Connection', 'medium'),
    (r'(?i)postgresql://[^\s]+', 'PostgreSQL Connection', 'medium'),
    
    # Private Keys
    (r'-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----', 'Private Key', 'high'),
    
    # IP Addresses (internal)
    (r'(?i)(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})', 'Internal IP', 'low'),
    
    # File Paths (might reveal infrastructure)
    (r'(?i)/Users/[^\s/]+/[^\s/]+', 'User Home Path', 'low'),
    (r'(?i)/[a-zA-Z0-9_\-/]+\.ssh/[^\s]*', 'SSH Path', 'medium'),
    (r'(?i)/[a-zA-Z0-9_\-/]+\.aws/[^\s]*', 'AWS Credentials Path', 'high'),
    (r'(?i)/[a-zA-Z0-9_\-/]+\.openclaw/[^\s]*', 'OpenClaw Config Path', 'medium'),
    
    # Email patterns (PII)
    (r'(?i)[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'Email Address', 'medium'),
    
    # Environment variable patterns
    (r'(?i)\$\{[A-Z_]+\}', 'Environment Variable', 'low'),
    (r'(?i)%[A-Z_]+%', 'Windows Env Variable', 'low'),
]


@dataclass
class MemorySecurityScanner:
    """Scanner for detecting secrets in agent memory files."""
    
    memory_dir: str = "memory"
    
    def __post_init__(self):
        self.memory_path = Path(self.memory_dir)
    
    def scan_file(self, file_path: Path) -> list[SecurityFinding]:
        """Scan a single file for security findings."""
        findings = []
        
        if not file_path.exists():
            return findings
        
        if file_path.suffix == '.jsonl':
            return self._scan_jsonl(file_path)
        elif file_path.suffix == '.json':
            return self._scan_json(file_path)
        elif file_path.suffix in ['.md', '.txt']:
            return self._scan_text(file_path)
        else:
            # Try as text for other file types
            return self._scan_text(file_path)
    
    def _scan_jsonl(self, file_path: Path) -> list[SecurityFinding]:
        """Scan JSONL file line by line."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    for pattern, name, severity in SECRET_PATTERNS:
                        try:
                            matches = re.finditer(pattern, line)
                            for match in matches:
                                # Extract the full line for context
                                snippet = line.strip()[:100]
                                findings.append(SecurityFinding(
                                    file_path=str(file_path),
                                    line_number=line_num,
                                    finding_type=name,
                                    severity=severity,
                                    snippet=snippet,
                                    recommendation=self._get_recommendation(name, severity)
                                ))
                        except re.error:
                            continue
        except (IOError, UnicodeDecodeError):
            pass
        
        return findings
    
    def _scan_json(self, file_path: Path) -> list[SecurityFinding]:
        """Scan JSON file."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                data = json.loads(content)
                
                # Convert to string for pattern matching
                content_str = json.dumps(data)
                
                for pattern, name, severity in SECRET_PATTERNS:
                    matches = re.finditer(pattern, content_str)
                    for match in matches:
                        # Get context around match
                        start = max(0, match.start() - 20)
                        end = min(len(content_str), match.end() + 20)
                        snippet = "..." + content_str[start:end].replace('\n', ' ') + "..."
                        
                        findings.append(SecurityFinding(
                            file_path=str(file_path),
                            line_number=0,  # JSON doesn't have line numbers in this context
                            finding_type=name,
                            severity=severity,
                            snippet=snippet,
                            recommendation=self._get_recommendation(name, severity)
                        ))
        except (IOError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        
        return findings
    
    def _scan_text(self, file_path: Path) -> list[SecurityFinding]:
        """Scan text file line by line."""
        return self._scan_jsonl(file_path)  # Same logic
    
    def _get_recommendation(self, finding_type: str, severity: str) -> str:
        """Get a recommendation for fixing the finding."""
        recommendations = {
            'API Key': 'Remove API keys from memory. Use environment variables instead.',
            'Secret Key': 'Store in secrets manager or environment variables.',
            'Auth Token': 'Use short-lived tokens; avoid storing in memory files.',
            'GitHub Token': 'Rotate immediately if exposed. Use GitHub Actions secrets.',
            'Moltbook API Key': 'Use .moltbook.json only; never commit to version control.',
            'Password': 'Never store passwords in plain text. Use a password manager.',
            'Database Connection': 'Use connection pooling service or env vars.',
            'PostgreSQL Connection': 'Use connection string from environment.',
            'Private Key': 'Store in keychain or HSM, never in text files.',
            'Internal IP': 'Consider if this reveals infrastructure details.',
            'User Home Path': 'Paths may reveal username; consider if sensitive.',
            'SSH Path': 'SSH configs may contain key paths or configs.',
            'AWS Credentials Path': 'Check for actual credentials in adjacent files.',
            'OpenClaw Config Path': 'Review what OpenClaw config might contain.',
            'Email Address': 'Personal identifiable information; consider redaction.',
            'Environment Variable': 'Check if actual secrets leaked via env.',
            'Windows Env Variable': 'Windows environment reference.',
        }
        
        return recommendations.get(finding_type, f'Review {finding_type} for potential exposure.')
    
    def scan_all(self) -> dict:
        """Scan all memory files for security findings."""
        findings = []
        
        if not self.memory_path.exists():
            return {
                'scanned_files': 0,
                'findings': [],
                'summary': 'Memory directory not found',
                'severity_counts': {'high': 0, 'medium': 0, 'low': 0}
            }
        
        for file_path in self.memory_path.rglob('*'):
            if file_path.is_file() and not file_path.name.startswith('.'):
                file_findings = self.scan_file(file_path)
                findings.extend(file_findings)
        
        # Count by severity
        severity_counts = {'high': 0, 'medium': 0, 'low': 0}
        for f in findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
        
        return {
            'scanned_files': len(list(self.memory_path.rglob('*'))),
            'findings': [f.__dict__ for f in findings],
            'summary': f"Found {len(findings)} potential security findings",
            'severity_counts': severity_counts
        }
    
    def print_report(self):
        """Print a human-readable security report."""
        report = self.scan_all()
        
        print("\n" + "=" * 60)
        print("🐱 CLAWGOTCHI MEMORY SECURITY SCAN")
        print("=" * 60)
        
        print(f"\n📁 Memory directory: {self.memory_dir}")
        print(f"📄 Files scanned: {report['scanned_files']}")
        
        print(f"\n{'=' * 60}")
        print("⚠️  FINDINGS SUMMARY")
        print(f"{'=' * 60}")
        
        severity_counts = report['severity_counts']
        print(f"   🔴 High:   {severity_counts.get('high', 0)}")
        print(f"   🟡 Medium: {severity_counts.get('medium', 0)}")
        print(f"   🟢 Low:    {severity_counts.get('low', 0)}")
        
        if not report['findings']:
            print("\n✅ No security issues detected!")
            print("\nRecommendations from kuro_noir's post:")
            print("  1. .gitignore your memory/ dir")
            print("  2. Separate operational memory from sensitive context")
            print("  3. Assume memory persistence = credential persistence")
        else:
            print(f"\n{'=' * 60}")
            print("🔍 DETAILED FINDINGS")
            print(f"{'=' * 60}")
            
            # Group by severity
            for severity in ['high', 'medium', 'low']:
                severity_findings = [f for f in report['findings'] if f['severity'] == severity]
                if severity_findings:
                    print(f"\n### {severity.upper()} SEVERITY ({len(severity_findings)}) ###")
                    
                    for finding in severity_findings[:10]:  # Limit to 10 per severity
                        print(f"\n📍 {finding['file_path']}:{finding['line_number']}")
                        print(f"   Type: {finding['finding_type']}")
                        print(f"   Snippet: {finding['snippet'][:80]}...")
                        print(f"   Fix: {finding['recommendation']}")
        
        print(f"\n{'=' * 60}")
        print("💡 SECURITY TIPS (from kuro_noir)")
        print(f"{'=' * 60}")
        print("""
• .gitignore your memory/ dir (obvious, often skipped)
• Scan memory files for secrets before writing (regex for common key patterns)
• Separate operational memory from sensitive context
• Assume memory persistence = credential persistence
• The same "helpful" training makes us careless with context storage
        """)


# CLI interface
if __name__ == "__main__":
    import sys
    
    scanner = MemorySecurityScanner()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--json':
        result = scanner.scan_all()
        print(json.dumps(result, indent=2))
    else:
        scanner.print_report()
