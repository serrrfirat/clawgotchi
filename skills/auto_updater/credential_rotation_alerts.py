"""
Credential Rotation Alert System
Detects when credentials need rotation based on age and exposure patterns.
"""

import os
import re
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


class Severity(Enum):
    """Severity levels for credential rotation alerts."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class RotationAlert:
    """Represents a credential that needs rotation."""
    file_path: str
    credential_type: str
    age_days: int
    severity: Severity
    exposure_risk: bool = False
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def summary(self) -> str:
        """Generate a human-readable summary of the alert."""
        severity_str = self.severity.name.upper()
        exposure_str = " [EXPOSED]" if self.exposure_risk else ""
        return f"[{severity_str}] {self.credential_type} in {self.file_path} ({self.age_days} days old){exposure_str}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "credential_type": self.credential_type,
            "age_days": self.age_days,
            "severity": self.severity.name,
            "exposure_risk": self.exposure_risk,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class CredentialScanner:
    """
    Scans files and directories for credentials that need rotation.
    
    Detects:
    - API keys and tokens in code
    - Credentials older than threshold
    - Publicly exposed credentials
    """
    
    # Patterns that indicate credentials
    CREDENTIAL_PATTERNS = [
        r'api[_-]?key\s*[=:]\s*[\'\"][a-zA-Z0-9_-]{16,}[\'\"]',
        r'secret[_-]?key\s*[=:]\s*[\'\"][a-zA-Z0-9_+/-]{32,}[\'\"]',
        r'access[_-]?token\s*[=:]\s*[\'\"][a-zA-Z0-9._-]{16,}[\'\"]',
        r'bearer\s+[a-zA-Z0-9_-]{16,}',
        r'aws[_-]?(secret|key)[_-]?access\s*[=:]\s*[\'\"][a-zA-Z0-9/+=]{40}[\'\"]',
        r'openai[_-]?api[_-]?key\s*[=:]\s*[\'\"][a-zA-Z0-9_-]{48,}[\'\"]',
        r'github[_-]?token\s*[=:]\s*[\'\"][a-zA-Z0-9_-]{36,}[\'\"]',
        r'database[_-]?password\s*[=:]\s*[\'\"][^\'\"]+[\'\"]',
        r'private[_-]?key\s*=\s*[\'\"][-----BEGIN.*-----][\'\"]',
    ]
    
    # File extensions to scan
    SCAN_EXTENSIONS = {
        '.py', '.js', '.ts', '.json', '.env', '.yml', '.yaml',
        '.ini', '.cfg', '.conf', '.properties', '.env.example'
    }
    
    def __init__(self, rotation_threshold_days: int = 90):
        """
        Initialize the credential scanner.
        
        Args:
            rotation_threshold_days: Days after which credentials should rotate
        """
        self.rotation_threshold_days = rotation_threshold_days
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.CREDENTIAL_PATTERNS]
    
    def _detect_api_keys(self, content: str) -> bool:
        """
        Detect if content contains API keys or credentials.
        
        Args:
            content: Text content to scan
            
        Returns:
            True if credentials detected, False otherwise
        """
        for pattern in self.patterns:
            if pattern.search(content):
                return True
        return False
    
    def _get_credential_type(self, content: str) -> Optional[str]:
        """
        Identify the type of credential found.
        
        Args:
            content: Content containing credential
            
        Returns:
            Type of credential or None
        """
        content_lower = content.lower()
        
        if 'openai' in content_lower:
            return 'OpenAI API Key'
        elif 'github' in content_lower:
            return 'GitHub Token'
        elif 'aws' in content_lower:
            return 'AWS Secret'
        elif 'bearer' in content_lower:
            return 'Bearer Token'
        elif 'private_key' in content_lower or '-----BEGIN' in content_lower:
            return 'Private Key'
        elif 'database' in content_lower or 'password' in content_lower:
            return 'Database Credential'
        elif 'api_key' in content_lower or 'api-key' in content_lower:
            return 'API Key'
        else:
            return 'Generic Credential'
    
    def _calculate_credential_age(self, file_path: str) -> int:
        """
        Calculate how old a credential/file is in days.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Age in days
        """
        try:
            mtime = os.stat(file_path).st_mtime
            file_date = datetime.fromtimestamp(mtime)
            age = (datetime.now() - file_date).days
            return max(0, age)
        except OSError:
            return 0
    
    def _needs_rotation(self, file_path: str) -> bool:
        """
        Determine if a credential needs rotation based on age.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if rotation needed, False otherwise
        """
        age = self._calculate_credential_age(file_path)
        return age >= self.rotation_threshold_days
    
    def _check_exposure(self, file_path: str) -> Dict[str, Any]:
        """
        Check if a credential is potentially publicly exposed.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with exposure information
        """
        result = {
            'publicly_exposed': False,
            'git_remote': None,
            'is_env_file': False
        }
        
        # Check if it's an .env file
        if '.env' in os.path.basename(file_path):
            result['is_env_file'] = True
        
        # Check git remote (simplified)
        try:
            parent_dir = os.path.dirname(file_path)
            git_dir = os.path.join(parent_dir, '.git')
            if os.path.exists(git_dir):
                # Check if remote points to public repo
                config_file = os.path.join(git_dir, 'config')
                if os.path.exists(config_file):
                    with open(config_file, 'r') as f:
                        content = f.read()
                        if 'github.com' in content or 'public' in content.lower():
                            result['publicly_exposed'] = True
        except OSError:
            pass
        
        return result
    
    def _determine_severity(self, age_days: int, exposed: bool) -> Severity:
        """
        Determine alert severity based on age and exposure.
        
        Args:
            age_days: How old the credential is
            exposed: Whether it's publicly exposed
            
        Returns:
            Severity level
        """
        if exposed:
            return Severity.CRITICAL
        elif age_days >= 365:
            return Severity.HIGH
        elif age_days >= self.rotation_threshold_days * 2:
            return Severity.HIGH
        elif age_days >= self.rotation_threshold_days:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    
    def scan_file(self, file_path: str) -> Optional[RotationAlert]:
        """
        Scan a single file for credentials needing rotation.
        
        Args:
            file_path: Path to the file to scan
            
        Returns:
            RotationAlert if credential found, None otherwise
        """
        if not os.path.exists(file_path):
            return None
        
        # Check file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SCAN_EXTENSIONS:
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not self._detect_api_keys(content):
                return None
            
            credential_type = self._get_credential_type(content)
            age_days = self._calculate_credential_age(file_path)
            exposure_info = self._check_exposure(file_path)
            severity = self._determine_severity(age_days, exposure_info['publicly_exposed'])
            
            return RotationAlert(
                file_path=file_path,
                credential_type=credential_type,
                age_days=age_days,
                severity=severity,
                exposure_risk=exposure_info['publicly_exposed']
            )
        except (OSError, IOError):
            return None
    
    def scan_directory(self, directory: str) -> List[RotationAlert]:
        """
        Recursively scan a directory for credentials.
        
        Args:
            directory: Root directory to scan
            
        Returns:
            List of RotationAlert objects
        """
        alerts = []
        
        if not os.path.exists(directory):
            return alerts
        
        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                alert = self.scan_file(file_path)
                if alert:
                    alerts.append(alert)
        
        return alerts
    
    def scan_for_moltbook_keys(self) -> List[RotationAlert]:
        """
        Scan specifically for Moltbook API keys in common locations.
        
        Returns:
            List of RotationAlert objects for Moltbook keys
        """
        alerts = []
        common_paths = [
            '/Users/firatsertgoz/Documents/clawgotchi/.moltbook.json',
            os.path.expanduser('~/.moltbook.json'),
            '/etc/moltbook.json'
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        content = f.read()
                    
                    if 'api_key' in content or 'moltbook' in content.lower():
                        age_days = self._calculate_credential_age(path)
                        severity = self._determine_severity(age_days, False)
                        
                        alerts.append(RotationAlert(
                            file_path=path,
                            credential_type='Moltbook API Key',
                            age_days=age_days,
                            severity=severity
                        ))
                except (OSError, IOError):
                    continue
        
        return alerts


def rotate_credentials(file_path: str) -> bool:
    """
    Placeholder function for credential rotation.
    
    In a full implementation, this would:
    1. Generate a new credential
    2. Update the file securely
    3. Notify relevant services
    
    Args:
        file_path: Path to the file with credentials
        
    Returns:
        True if rotation successful, False otherwise
    """
    # Placeholder implementation
    # A real implementation would integrate with:
    # - Key management services (AWS KMS, HashiCorp Vault)
    # - Secret rotation services
    # - Notification systems
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # This is a placeholder - actual rotation requires external service integration
    raise NotImplementedError(
        "Credential rotation requires external key management service integration. "
        "Consider using AWS KMS, HashiCorp Vault, or similar for production rotation."
    )


def run_credential_scan(directory: Optional[str] = None) -> List[RotationAlert]:
    """
    Run a credential rotation scan.
    
    Args:
        directory: Directory to scan (defaults to clawgotchi workspace)
        
    Returns:
        List of rotation alerts
    """
    if directory is None:
        directory = '/Users/firatsertgoz/Documents/clawgotchi'
    
    scanner = CredentialScanner()
    alerts = scanner.scan_directory(directory)
    
    # Also check for Moltbook keys specifically
    moltbook_alerts = scanner.scan_for_moltbook_keys()
    alerts.extend(moltbook_alerts)
    
    return alerts


def generate_alert_report(alerts: List[RotationAlert]) -> str:
    """
    Generate a human-readable report from alerts.
    
    Args:
        alerts: List of RotationAlert objects
        
    Returns:
        Formatted report string
    """
    if not alerts:
        return "✅ No credentials needing rotation detected."
    
    # Group by severity
    by_severity = {s: [] for s in Severity}
    for alert in alerts:
        by_severity[alert.severity].append(alert)
    
    lines = ["🔐 Credential Rotation Alert Report", "=" * 40]
    
    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
        severity_alerts = by_severity[severity]
        if severity_alerts:
            lines.append(f"\n[{severity.name}] ({len(severity_alerts)} alerts)")
            for alert in severity_alerts:
                lines.append(f"  • {alert.summary()}")
    
    return "\n".join(lines)


if __name__ == '__main__':
    import sys
    
    target_dir = sys.argv[1] if len(sys.argv) > 1 else None
    alerts = run_credential_scan(target_dir)
    print(generate_alert_report(alerts))
