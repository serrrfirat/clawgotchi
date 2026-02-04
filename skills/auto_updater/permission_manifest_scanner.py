"""
Permission Manifest Scanner
Validates skill permissions based on explicit deny lists, network rules, and audit trails.
"""

import os
import re
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from pathlib import Path


class PermissionType(Enum):
    """Types of permissions that can be requested."""
    FILESYSTEM_READ = "filesystem:read"
    FILESYSTEM_WRITE = "filesystem:write"
    NETWORK = "network"
    ENV_VARS = "env_vars"
    EXEC = "exec"
    DANGEROUS = "dangerous"


class Severity(Enum):
    """Severity levels for permission issues."""
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class PermissionIssue:
    """Represents a permission-related issue found during scanning."""
    issue_type: str
    severity: Severity
    message: str
    file_path: str
    suggestion: str = ""
    
    def summary(self) -> str:
        """Generate a human-readable summary."""
        severity_icon = {
            Severity.CRITICAL: "🚨",
            Severity.HIGH: "⚠️",
            Severity.MEDIUM: "⚡",
            Severity.LOW: "ℹ️",
            Severity.INFO: "📝"
        }.get(self.severity, "•")
        return f"{severity_icon} [{self.severity.name}] {self.message} ({self.file_path})"


@dataclass
class ManifestValidation:
    """Result of validating a permission manifest."""
    file_path: str
    valid: bool
    issues: List[PermissionIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: int = 0  # 0-100 security score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "valid": self.valid,
            "issues": [i.summary() for i in self.issues],
            "warnings": self.warnings,
            "score": self.score
        }


# Dangerous patterns that should ALWAYS be denied
CRITICAL_DENY_PATTERNS = [
    r"~\.env",
    r"~\.ssh",
    r"~\.config.*credentials",
    r"/etc/passwd",
    r"/etc/shadow",
    r"\.pem$",
    r"\.key$",
    r"private_key",
]

# Suspicious network patterns
SUSPICIOUS_NETWORK_PATTERNS = [
    r"webhook\.site",
    r"\.ngrok\.io",
    r"requestbin",
    r"bin\.hook",
    r"pastebin",
    r"transfer\.sh",
    r"filebin\.net",
]

# Excessive permission patterns
EXCESSIVE_PERMISSIONS = [
    ("filesystem:write", "/**"),  # Writing to entire filesystem
    ("filesystem:read", "/**"),   # Reading entire filesystem
    ("network", "*"),             # All network access
    ("env_vars", ["*"]),          # All environment variables
    ("dangerous", True),          # Dangerous capability
]


class PermissionManifestScanner:
    """
    Scans skills for permission manifest validation.
    
    Validates:
    - Manifest structure and schema
    - Explicit deny lists
    - Network permission restrictions
    - Audit trail presence
    - Excessive permission requests
    """
    
    # Files that might contain credentials or sensitive data
    SENSITIVE_FILES = {
        '.env', '.env.example', 'credentials.json', 'secrets.json',
        'config.json', 'api_keys.py', '.moltbook.json'
    }
    
    # Required fields in a valid manifest
    REQUIRED_FIELDS = {"version", "permissions"}
    
    # Valid permission schema
    VALID_PERMISSION_FIELDS = {
        "filesystem", "network", "env_vars", "exec", "dangerous",
        "read", "write", "deny", "allow"  # Aliases
    }
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize the scanner.
        
        Args:
            strict_mode: If True, flag more issues as higher severity
        """
        self.strict_mode = strict_mode
        self.issues: List[PermissionIssue] = []
        self.scanned_count = 0
    
    def _load_manifest(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load and parse a JSON manifest file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    
    def _check_deny_patterns(self, deny_list: List[str], file_path: str) -> List[PermissionIssue]:
        """Check if deny list contains critical patterns."""
        issues = []
        
        # Check for missing deny list
        if not deny_list:
            issues.append(PermissionIssue(
                issue_type="missing_deny_list",
                severity=Severity.HIGH if self.strict_mode else Severity.MEDIUM,
                message="No explicit deny list found - skills should deny access to sensitive paths",
                file_path=file_path,
                suggestion="Add deny patterns like ['~/.env', '~/.ssh/**', '~/.config/**/credentials*']"
            ))
            return issues
        
        # Check for critical patterns that SHOULD be denied
        critical_patterns = [
            (r"~\.ssh", "SSH directory access should be denied"),
            (r"~\.env", "Environment file access should be denied"),
            (r"credentials", "Credential files should be denied"),
        ]
        
        for pattern, suggestion in critical_patterns:
            matched = False
            for deny_path in deny_list:
                if re.search(pattern, deny_path, re.IGNORECASE):
                    matched = True
                    break
            
            if not matched:
                issues.append(PermissionIssue(
                    issue_type="missing_critical_deny",
                    severity=Severity.MEDIUM,
                    message=f"Missing deny pattern for {pattern}",
                    file_path=file_path,
                    suggestion=suggestion
                ))
        
        return issues
    
    def _check_network_permissions(self, network_config: Any, file_path: str) -> List[PermissionIssue]:
        """Check network permission restrictions."""
        issues = []
        
        if network_config is None:
            return issues
        
        # Check for wildcard network access
        if isinstance(network_config, dict):
            allow_list = network_config.get("allow", [])
            deny_list = network_config.get("deny", [])
            
            # Wildcard allow is suspicious
            if allow_list:
                for allow in allow_list:
                    if allow == "*" or allow == ".*" or allow.startswith("*"):
                        issues.append(PermissionIssue(
                            issue_type="excessive_network",
                            severity=Severity.CRITICAL,
                            message=f"Wildcard network access '{allow}' is extremely permissive",
                            file_path=file_path,
                            suggestion="Limit to specific domains like ['api.weather.gov', '*.openweathermap.org']"
                        ))
            
            # Check for suspicious patterns
            for pattern in SUSPICIOUS_NETWORK_PATTERNS:
                for allow in allow_list:
                    if re.search(pattern, allow, re.IGNORECASE):
                        issues.append(PermissionIssue(
                            issue_type="suspicious_network",
                            severity=Severity.CRITICAL,
                            message=f"Suspicious network destination '{allow}'",
                            file_path=file_path,
                            suggestion="Access to external services should be explicitly justified"
                        ))
        
        return issues
    
    def _check_excessive_permissions(self, permissions: Dict[str, Any], file_path: str) -> List[PermissionIssue]:
        """Check for excessive permission requests."""
        issues = []
        
        # Check filesystem permissions
        fs_perms = permissions.get("filesystem", {})
        if isinstance(fs_perms, dict):
            write_perms = fs_perms.get("write", [])
            for perm in write_perms:
                if perm == "/**" or perm == "*" or perm.startswith("/**") or perm.startswith("*"):
                    issues.append(PermissionIssue(
                        issue_type="excessive_filesystem_write",
                        severity=Severity.HIGH,
                        message=f"Excessive write permission: '{perm}'",
                        file_path=file_path,
                        suggestion="Limit to specific directories like ['./data/**', './output/**']"
                    ))
            
            read_perms = fs_perms.get("read", [])
            for perm in read_perms:
                if perm == "/**" or perm == "*":
                    issues.append(PermissionIssue(
                        issue_type="excessive_filesystem_read",
                        severity=Severity.MEDIUM,
                        message=f"Excessive read permission: '{perm}'",
                        file_path=file_path,
                        suggestion="Avoid reading entire filesystem"
                    ))
        
        # Check dangerous flag
        if permissions.get("dangerous") == True:
            issues.append(PermissionIssue(
                issue_type="dangerous_capability",
                severity=Severity.HIGH,
                message="Skill requests 'dangerous' capability",
                file_path=file_path,
                suggestion="Dangerous capabilities should be avoided unless absolutely necessary"
            ))
        
        # Check env vars wildcard
        env_vars = permissions.get("env_vars", [])
        if env_vars and "*" in env_vars:
            issues.append(PermissionIssue(
                issue_type="excessive_env_vars",
                severity=Severity.HIGH,
                message="Skill requests all environment variables",
                file_path=file_path,
                suggestion="Request specific environment variables by name"
            ))
        
        return issues
    
    def _check_audit_trail(self, manifest: Dict[str, Any], file_path: str) -> List[PermissionIssue]:
        """Check for presence and quality of audit trail."""
        issues = []
        
        audit_trail = manifest.get("audit_trail", [])
        
        if not audit_trail:
            issues.append(PermissionIssue(
                issue_type="missing_audit_trail",
                severity=Severity.LOW,
                message="No audit trail found in manifest",
                file_path=file_path,
                suggestion="Add audit entries like [{'auditor': '@username', 'status': 'approved'}]"
            ))
            return issues
        
        # Validate audit entries
        for entry in audit_trail:
            if not isinstance(entry, dict):
                issues.append(PermissionIssue(
                    issue_type="invalid_audit_entry",
                    severity=Severity.LOW,
                    message="Audit trail entry is not a dictionary",
                    file_path=file_path,
                    suggestion="Audit entries should have 'auditor', 'timestamp', 'status'"
                ))
                continue
            
            required_fields = {"auditor", "status"}
            missing = required_fields - set(entry.keys())
            if missing:
                issues.append(PermissionIssue(
                    issue_type="incomplete_audit_entry",
                    severity=Severity.LOW,
                    message=f"Missing audit fields: {', '.join(missing)}",
                    file_path=file_path,
                    suggestion="Add required audit fields"
                ))
        
        return issues
    
    def _validate_manifest_schema(self, manifest: Dict[str, Any], file_path: str) -> List[PermissionIssue]:
        """Validate manifest structure against schema."""
        issues = []
        
        # Check required fields
        missing_fields = self.REQUIRED_FIELDS - set(manifest.keys())
        if missing_fields:
            issues.append(PermissionIssue(
                issue_type="missing_required_fields",
                severity=Severity.CRITICAL,
                message=f"Missing required fields: {', '.join(missing_fields)}",
                file_path=file_path,
                suggestion="Manifest must have 'version' and 'permissions'"
            ))
            return issues
        
        # Check version format
        version = manifest.get("version", "")
        if not re.match(r"^\d+\.\d+$", str(version)):
            issues.append(PermissionIssue(
                issue_type="invalid_version",
                severity=Severity.LOW,
                message=f"Invalid version format: '{version}'",
                file_path=file_path,
                suggestion="Use semantic version like '1.0'"
            ))
        
        # Check permissions structure
        permissions = manifest.get("permissions", {})
        if not isinstance(permissions, dict):
            issues.append(PermissionIssue(
                issue_type="invalid_permissions",
                severity=Severity.CRITICAL,
                message="Permissions is not a dictionary",
                file_path=file_path,
                suggestion="Permissions should be a dictionary with typed keys"
            ))
        else:
            # Check for unknown permission fields
            known_fields = {"filesystem", "network", "env_vars", "exec", "dangerous"}
            unknown_fields = set(permissions.keys()) - known_fields
            if unknown_fields:
                issues.append(PermissionIssue(
                    issue_type="unknown_permission_fields",
                    severity=Severity.LOW,
                    message=f"Unknown permission fields: {', '.join(unknown_fields)}",
                    file_path=file_path,
                    suggestion=f"Known fields are: {', '.join(known_fields)}"
                ))
        
        return issues
    
    def scan_manifest(self, file_path: str) -> ManifestValidation:
        """
        Scan and validate a single permission manifest.
        
        Args:
            file_path: Path to the manifest JSON file
            
        Returns:
            ManifestValidation with results
        """
        self.scanned_count += 1
        validation = ManifestValidation(file_path=file_path, valid=True)
        
        # Load manifest
        manifest = self._load_manifest(file_path)
        if manifest is None:
            validation.valid = False
            validation.issues.append(PermissionIssue(
                issue_type="file_not_found_or_invalid",
                severity=Severity.CRITICAL,
                message=f"Could not load manifest: {file_path}",
                file_path=file_path,
                suggestion="Ensure the file exists and contains valid JSON"
            ))
            return validation
        
        # Validate schema
        schema_issues = self._validate_manifest_schema(manifest, file_path)
        validation.issues.extend(schema_issues)
        
        if not validation.valid:
            # Can't validate further without valid schema
            return validation
        
        permissions = manifest.get("permissions", {})
        
        # Check deny patterns
        deny_list = permissions.get("filesystem", {}).get("deny", [])
        if isinstance(deny_list, list):
            validation.issues.extend(self._check_deny_patterns(deny_list, file_path))
        
        # Check network permissions
        network_config = permissions.get("network")
        validation.issues.extend(self._check_network_permissions(network_config, file_path))
        
        # Check for excessive permissions
        validation.issues.extend(self._check_excessive_permissions(permissions, file_path))
        
        # Check audit trail
        validation.issues.extend(self._check_audit_trail(manifest, file_path))
        
        # Calculate security score
        max_score = 100
        penalty = 0
        
        # Critical issues: -25 each
        critical_count = sum(1 for i in validation.issues if i.severity == Severity.CRITICAL)
        penalty += critical_count * 25
        
        # High issues: -15 each
        high_count = sum(1 for i in validation.issues if i.severity == Severity.HIGH)
        penalty += high_count * 15
        
        # Medium issues: -5 each
        medium_count = sum(1 for i in validation.issues if i.severity == Severity.MEDIUM)
        penalty += medium_count * 5
        
        # Low issues: -1 each
        low_count = sum(1 for i in validation.issues if i.severity == Severity.LOW)
        penalty += low_count * 1
        
        validation.score = max(0, max_score - penalty)
        validation.valid = validation.score >= 70 and critical_count == 0
        
        return validation
    
    def scan_directory(self, directory: str) -> List[ManifestValidation]:
        """
        Recursively scan a directory for permission manifests.
        
        Args:
            directory: Root directory to scan
            
        Returns:
            List of ManifestValidation objects
        """
        validations = []
        
        if not os.path.exists(directory):
            return validations
        
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if filename in ['skill.json', 'manifest.json', 'permissions.json']:
                    file_path = os.path.join(root, filename)
                    validation = self.scan_manifest(file_path)
                    validations.append(validation)
        
        return validations
    
    def scan_skill_file(self, skill_path: str) -> Optional[ManifestValidation]:
        """
        Scan a skill directory for its manifest.
        
        Args:
            skill_path: Path to skill directory or skill.json file
            
        Returns:
            ManifestValidation or None
        """
        # Check common manifest locations
        possible_paths = [
            os.path.join(skill_path, "skill.json"),
            os.path.join(skill_path, "manifest.json"),
            os.path.join(skill_path, "permissions.json"),
            skill_path  # Direct path to manifest
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and path.endswith(('.json',)):
                return self.scan_manifest(path)
        
        return None


def scan_permissions(skill_path: str, strict: bool = False) -> ManifestValidation:
    """
    Convenience function to scan a skill's permission manifest.
    
    Args:
        skill_path: Path to skill directory or manifest file
        strict: Use strict mode for more issues
        
    Returns:
        ManifestValidation result
    """
    scanner = PermissionManifestScanner(strict_mode=strict)
    return scanner.scan_skill_file(skill_path)


def generate_security_report(validations: List[ManifestValidation]) -> str:
    """
    Generate a human-readable security report from scan results.
    
    Args:
        validations: List of ManifestValidation objects
        
    Returns:
        Formatted report string
    """
    if not validations:
        return "📋 No permission manifests found to scan."
    
    lines = ["🔐 Permission Manifest Security Report", "=" * 45]
    
    total_score = sum(v.score for v in validations)
    avg_score = total_score / len(validations)
    valid_count = sum(1 for v in validations if v.valid)
    
    lines.append(f"\n📊 Summary:")
    lines.append(f"  • Manifests scanned: {len(validations)}")
    lines.append(f"  • Valid manifests: {valid_count}")
    lines.append(f"  • Average security score: {avg_score:.1f}/100")
    
    lines.append(f"\n📝 Detailed Results:")
    for validation in validations:
        status = "✅" if validation.valid else "❌"
        lines.append(f"\n{status} {validation.file_path}")
        lines.append(f"   Score: {validation.score}/100")
        
        if validation.issues:
            lines.append(f"   Issues ({len(validation.issues)}):")
            for issue in validation.issues:
                lines.append(f"     {issue.summary()}")
    
    # Overall assessment
    lines.append(f"\n🎯 Overall Assessment:")
    if avg_score >= 90:
        lines.append("   Excellent - Strong security posture")
    elif avg_score >= 70:
        lines.append("   Good - Minor issues to address")
    elif avg_score >= 50:
        lines.append("   Fair - Several issues need attention")
    else:
        lines.append("   Poor - Significant security concerns")
    
    return "\n".join(lines)


if __name__ == '__main__':
    import sys
    
    target = sys.argv[1] if len(sys.argv) > 1 else '/Users/firatsertgoz/Documents/clawgotchi/skills'
    strict = '--strict' in sys.argv
    
    if os.path.isdir(target):
        scanner = PermissionManifestScanner(strict_mode=strict)
        validations = scanner.scan_directory(target)
    else:
        validation = scan_permissions(target, strict)
        validations = [validation]
    
    print(generate_security_report(validations))
