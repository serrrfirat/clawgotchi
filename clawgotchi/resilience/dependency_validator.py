"""Dependency Manifest Validator.

Validates dependency configurations against security best practices
for preventing dependency confusion attacks.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ValidationCheck(Enum):
    """Types of validation checks to perform."""

    SCOPED_NAME = "scoped_name"
    PRIVATE_REGISTRY = "private_registry"
    LOCK_FILE = "lock_file"
    NET_INSTALL_DISABLED = "net_install_disabled"


class ViolationType(Enum):
    """Severity levels for validation violations."""

    HIGH_RISK = "HIGH_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    LOW_RISK = "LOW_RISK"
    INFO = "INFO"


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    check: ValidationCheck
    passed: bool
    message: str
    severity: Optional[ViolationType] = None
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "check": self.check.value,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity.value if self.severity else None,
            "recommendations": self.recommendations,
        }


@dataclass
class DependencyManifest:
    """Manifest describing a dependency for validation."""

    package_name: str
    version: str
    registry: Optional[str] = None
    lock_file: Optional[str] = None
    net_install_allowed: Optional[bool] = None

    def to_dict(self) -> dict:
        """Convert manifest to dictionary."""
        return {
            "package_name": self.package_name,
            "version": self.version,
            "registry": self.registry,
            "lock_file": self.lock_file,
            "net_install_allowed": self.net_install_allowed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DependencyManifest":
        """Create manifest from dictionary."""
        return cls(
            package_name=data["package_name"],
            version=data["version"],
            registry=data.get("registry"),
            lock_file=data.get("lock_file"),
            net_install_allowed=data.get("net_install_allowed"),
        )


class DependencyValidator:
    """Validates dependency configurations against security best practices."""

    # Private registry patterns (not public npm/pypi)
    PRIVATE_REGISTRY_PATTERNS = [
        r"^https?://[^/]*\.acme\.com",
        r"^https?://[^/]*\.corp\.com",
        r"^https?://[^/]*\.internal",
        r"^https?://[^/]*\.intranet",
        r"^https?://localhost",
        r"^https?://127\.0\.0\.1",
        r"^https?://[^/]*/artifactory/",
        r"^https?://[^/]*/nexus/",
        r"^https?://[^/]*/verdaccio",
    ]

    # Public registries that should not be used for internal packages
    PUBLIC_REGISTRY_PATTERNS = [
        r"^https?://registry\.npmjs\.org",
        r"^https?://registry\.yarnpkg\.com",
        r"^https?://pypi\.org",
        r"^https?://pypi\.simple",
        r"^https://registry\.nodeform\.ai",
    ]

    def __init__(self):
        """Initialize the validator."""
        self._private_pattern = re.compile(
            "(" + "|".join(self.PRIVATE_REGISTRY_PATTERNS) + ")"
        )
        self._public_pattern = re.compile(
            "(" + "|".join(self.PUBLIC_REGISTRY_PATTERNS) + ")"
        )

    def _is_scoped(self, package_name: str) -> bool:
        """Check if package name is scoped (for internal packages)."""
        return package_name.startswith("@")

    def _is_private_registry(self, registry_url: Optional[str]) -> Optional[bool]:
        """Check if registry URL is a private/internal registry."""
        if registry_url is None:
            return None
        if self._private_pattern.match(registry_url):
            return True
        if self._public_pattern.match(registry_url):
            return False
        # Unknown registry - assume might be private for safety
        return None

    def _lock_file_exists(self, lock_file: Optional[str]) -> Optional[bool]:
        """Check if lock file exists."""
        if lock_file is None:
            return None
        import os

        return os.path.exists(lock_file)

    def _check_scoped_name(
        self, manifest: DependencyManifest
    ) -> ValidationResult:
        """Check that internal packages use scoped names."""
        if self._is_scoped(manifest.package_name):
            return ValidationResult(
                check=ValidationCheck.SCOPED_NAME,
                passed=True,
                message=f"Package '{manifest.package_name}' is properly scoped",
            )
        else:
            return ValidationResult(
                check=ValidationCheck.SCOPED_NAME,
                passed=False,
                message=f"Package '{manifest.package_name}' is not scoped - dependency confusion risk",
                severity=ViolationType.HIGH_RISK,
                recommendations=[
                    "Use scoped package names for internal packages (e.g., @acme/package-name)",
                    "Scope all packages with your organization prefix",
                    "Consider using @<company-name>/<package-name> convention",
                ],
            )

    def _check_private_registry(
        self, manifest: DependencyManifest
    ) -> ValidationResult:
        """Check that internal packages use private registries."""
        if manifest.registry is None:
            return ValidationResult(
                check=ValidationCheck.PRIVATE_REGISTRY,
                passed=True,
                message="No registry specified - assuming public (INFO)",
                severity=ViolationType.INFO,
                recommendations=[
                    "Explicitly specify a private registry for internal packages",
                    "Configure .npmrc or pip.conf to enforce private registry usage",
                ],
            )

        is_private = self._is_private_registry(manifest.registry)

        if is_private is True:
            return ValidationResult(
                check=ValidationCheck.PRIVATE_REGISTRY,
                passed=True,
                message=f"Package uses private registry: {manifest.registry}",
            )
        elif is_private is False:
            return ValidationResult(
                check=ValidationCheck.PRIVATE_REGISTRY,
                passed=False,
                message=f"Package uses public registry '{manifest.registry}' - dependency confusion risk",
                severity=ViolationType.MEDIUM_RISK,
                recommendations=[
                    f"Configure {manifest.registry} to redirect internal packages to private registry",
                    "Set up .npmrc with registry=private-registry.acme.com",
                    "Use npm config set registry for private packages",
                ],
            )
        else:
            # Unknown registry - warn but don't fail
            return ValidationResult(
                check=ValidationCheck.PRIVATE_REGISTRY,
                passed=True,
                message=f"Registry '{manifest.registry}' is not recognized as public - manual review needed",
                severity=ViolationType.INFO,
                recommendations=[
                    "Verify this registry is indeed private/internal",
                    "Document approved private registries",
                ],
            )

    def _check_lock_file(self, manifest: DependencyManifest) -> ValidationResult:
        """Check that lock files are present for reproducibility."""
        if manifest.lock_file is None:
            return ValidationResult(
                check=ValidationCheck.LOCK_FILE,
                passed=True,
                message="No lock file specified (INFO)",
                severity=ViolationType.INFO,
                recommendations=[
                    "Use lock files for reproducible builds",
                    "Commit package-lock.json, yarn.lock, or pnpm-lock.yaml to version control",
                    "Run npm ci instead of npm install in CI",
                ],
            )

        exists = self._lock_file_exists(manifest.lock_file)

        if exists:
            return ValidationResult(
                check=ValidationCheck.LOCK_FILE,
                passed=True,
                message=f"Lock file '{manifest.lock_file}' exists",
            )
        else:
            return ValidationResult(
                check=ValidationCheck.LOCK_FILE,
                passed=False,
                message=f"Lock file '{manifest.lock_file}' not found",
                severity=ViolationType.HIGH_RISK,
                recommendations=[
                    "Ensure lock file is committed to version control",
                    "Run npm install/yarn install/pnpm install to generate lock file",
                    "Use npm ci in CI to use exact versions from lock file",
                ],
            )

    def _check_net_install(self, manifest: DependencyManifest) -> ValidationResult:
        """Check that net-install (install-time fetches) is disabled."""
        if manifest.net_install_allowed is None:
            return ValidationResult(
                check=ValidationCheck.NET_INSTALL_DISABLED,
                passed=True,
                message="Net-install setting not specified (INFO)",
                severity=ViolationType.INFO,
                recommendations=[
                    "Explicitly disable net-install in build scripts",
                    "Use pre-built artifacts from verified sources",
                    "Configure CI to block network access during install",
                ],
            )

        if not manifest.net_install_allowed:
            return ValidationResult(
                check=ValidationCheck.NET_INSTALL_DISABLED,
                passed=True,
                message="Net-install is properly disabled",
            )
        else:
            return ValidationResult(
                check=ValidationCheck.NET_INSTALL_DISABLED,
                passed=False,
                message="Net-install is enabled - potential supply chain risk",
                severity=ViolationType.HIGH_RISK,
                recommendations=[
                    "Disable net-install in build/runtime steps",
                    "Use pre-built artifacts from verified sources",
                    "Configure CI sandbox to block egress to public registries",
                ],
            )

    def _severity_to_score(self, severity: Optional[ViolationType]) -> int:
        """Convert severity to numeric score."""
        if severity is None:
            return 0
        scores = {
            ViolationType.HIGH_RISK: 30,
            ViolationType.MEDIUM_RISK: 15,
            ViolationType.LOW_RISK: 5,
            ViolationType.INFO: 0,
        }
        return scores.get(severity, 0)

    def validate(self, manifest: DependencyManifest) -> list[ValidationResult]:
        """Run all validation checks on a manifest.

        Args:
            manifest: The dependency manifest to validate

        Returns:
            List of validation results for each check
        """
        return [
            self._check_scoped_name(manifest),
            self._check_private_registry(manifest),
            self._check_lock_file(manifest),
            self._check_net_install(manifest),
        ]

    def get_summary(self, manifest: DependencyManifest) -> dict:
        """Get a summary of validation results.

        Args:
            manifest: The dependency manifest to validate

        Returns:
            Dictionary with summary information
        """
        results = self.validate(manifest)

        passed_checks = sum(1 for r in results if r.passed)
        failed_checks = sum(1 for r in results if not r.passed)
        total_checks = len(results)

        # Calculate score (100 minus penalties for failures)
        penalties = sum(self._severity_to_score(r.severity) for r in results if not r.passed)
        score = max(0, 100 - penalties)

        return {
            "passed": failed_checks == 0,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "score": score,
            "results": [r.to_dict() for r in results],
        }

    def get_recommendations(self, manifest: DependencyManifest) -> list[str]:
        """Get all recommendations for a manifest.

        Args:
            manifest: The dependency manifest to check

        Returns:
            List of recommendation strings
        """
        results = self.validate(manifest)
        recommendations = []

        for result in results:
            if result.recommendations:
                recommendations.extend(result.recommendations)

        return recommendations

    def validate_all(
        self, manifests: list[DependencyManifest]
    ) -> list[dict]:
        """Validate multiple manifests at once.

        Args:
            manifests: List of dependency manifests to validate

        Returns:
            List of summary dictionaries for each manifest
        """
        return [self.get_summary(m) for m in manifests]

    def get_risk_score(self, manifest: DependencyManifest) -> int:
        """Calculate a risk score for a manifest.

        Args:
            manifest: The dependency manifest to assess

        Returns:
            Risk score (0-100, higher is riskier)
        """
        results = self.validate(manifest)
        penalties = sum(self._severity_to_score(r.severity) for r in results if not r.passed)
        return min(100, penalties)
