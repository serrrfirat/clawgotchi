"""Tests for Dependency Manifest Validator.

Validates dependency configurations against security best practices.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from clawgotchi.resilience.dependency_validator import (
    DependencyManifest,
    DependencyValidator,
    ValidationCheck,
    ValidationResult,
    ViolationType,
)


class TestDependencyManifest:
    """Tests for DependencyManifest dataclass."""

    def test_manifest_creation(self):
        """Test creating a dependency manifest."""
        manifest = DependencyManifest(
            package_name="@acme/internal-lib",
            version="1.0.0",
            registry="private-registry.acme.com",
            lock_file="package-lock.json",
        )
        assert manifest.package_name == "@acme/internal-lib"
        assert manifest.version == "1.0.0"
        assert manifest.registry == "private-registry.acme.com"
        assert manifest.lock_file == "package-lock.json"

    def test_manifest_serialization(self):
        """Test manifest JSON serialization."""
        manifest = DependencyManifest(
            package_name="@acme/core",
            version="2.0.0",
            registry="internal",
            lock_file="yarn.lock",
        )
        data = manifest.to_dict()
        assert data["package_name"] == "@acme/core"
        assert data["version"] == "2.0.0"
        assert "lock_file" in data

    def test_manifest_deserialization(self):
        """Test manifest JSON deserialization."""
        data = {
            "package_name": "@test/pkg",
            "version": "1.2.3",
            "registry": "https://private.example.com",
            "lock_file": "pnpm-lock.yaml",
        }
        manifest = DependencyManifest.from_dict(data)
        assert manifest.package_name == "@test/pkg"
        assert manifest.lock_file == "pnpm-lock.yaml"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_result_pass(self):
        """Test a passing validation result."""
        result = ValidationResult(
            check=ValidationCheck.SCOPED_NAME,
            passed=True,
            message="Package name is properly scoped",
        )
        assert result.passed is True
        assert result.severity is None

    def test_result_fail_with_severity(self):
        """Test a failing validation result with severity."""
        result = ValidationResult(
            check=ValidationCheck.LOCK_FILE,
            passed=False,
            message="No lock file found",
            severity=ViolationType.HIGH_RISK,
        )
        assert result.passed is False
        assert result.severity == ViolationType.HIGH_RISK

    def test_result_recommendations(self):
        """Test validation result with recommendations."""
        result = ValidationResult(
            check=ValidationCheck.PRIVATE_REGISTRY,
            passed=False,
            message="Using public registry for internal package",
            severity=ViolationType.MEDIUM_RISK,
            recommendations=[
                "Configure npm to use private registry",
                "Set up .npmrc with registry preference",
            ],
        )
        assert len(result.recommendations) == 2


class TestViolationType:
    """Tests for ViolationType enum."""

    def test_violation_types_exist(self):
        """Test all expected violation types exist."""
        assert ViolationType.HIGH_RISK.value == "HIGH_RISK"
        assert ViolationType.MEDIUM_RISK.value == "MEDIUM_RISK"
        assert ViolationType.LOW_RISK.value == "LOW_RISK"
        assert ViolationType.INFO.value == "INFO"


class TestValidationCheck:
    """Tests for ValidationCheck enum."""

    def test_checks_exist(self):
        """Test all expected validation checks exist."""
        checks = [
            ValidationCheck.SCOPED_NAME,
            ValidationCheck.PRIVATE_REGISTRY,
            ValidationCheck.LOCK_FILE,
            ValidationCheck.NET_INSTALL_DISABLED,
        ]
        for check in checks:
            assert check is not None


class TestDependencyValidator:
    """Tests for DependencyValidator main class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.validator = DependencyValidator()

    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_scoped_name_pass(self):
        """Test validation passes for properly scoped package."""
        manifest = DependencyManifest(
            package_name="@acme/private-lib",
            version="1.0.0",
            registry="private",
        )
        results = self.validator.validate(manifest)
        scoped_result = next(r for r in results if r.check == ValidationCheck.SCOPED_NAME)
        assert scoped_result.passed is True

    def test_validate_scoped_name_fail(self):
        """Test validation fails for unscoped package name."""
        manifest = DependencyManifest(
            package_name="public-lib",
            version="1.0.0",
            registry="private",
        )
        results = self.validator.validate(manifest)
        scoped_result = next(r for r in results if r.check == ValidationCheck.SCOPED_NAME)
        assert scoped_result.passed is False
        assert scoped_result.severity == ViolationType.HIGH_RISK

    def test_validate_private_registry_pass(self):
        """Test validation passes for private registry."""
        manifest = DependencyManifest(
            package_name="@acme/core",
            version="1.0.0",
            registry="https://private-registry.acme.com",
        )
        results = self.validator.validate(manifest)
        registry_result = next(
            r for r in results if r.check == ValidationCheck.PRIVATE_REGISTRY
        )
        assert registry_result.passed is True

    def test_validate_private_registry_fail(self):
        """Test validation fails for public registry."""
        manifest = DependencyManifest(
            package_name="@acme/core",
            version="1.0.0",
            registry="https://registry.npmjs.org",
        )
        results = self.validator.validate(manifest)
        registry_result = next(
            r for r in results if r.check == ValidationCheck.PRIVATE_REGISTRY
        )
        assert registry_result.passed is False
        assert registry_result.severity == ViolationType.MEDIUM_RISK

    def test_validate_lock_file_exists(self):
        """Test validation passes when lock file exists."""
        lock_file = os.path.join(self.temp_dir, "package-lock.json")
        with open(lock_file, "w") as f:
            f.write('{"version": 1}')

        manifest = DependencyManifest(
            package_name="@acme/pkg",
            version="1.0.0",
            lock_file=lock_file,
        )
        results = self.validator.validate(manifest)
        lock_result = next(r for r in results if r.check == ValidationCheck.LOCK_FILE)
        assert lock_result.passed is True

    def test_validate_lock_file_missing(self):
        """Test validation fails when lock file is missing."""
        manifest = DependencyManifest(
            package_name="@acme/pkg",
            version="1.0.0",
            lock_file="/nonexistent/package-lock.json",
        )
        results = self.validator.validate(manifest)
        lock_result = next(r for r in results if r.check == ValidationCheck.LOCK_FILE)
        assert lock_result.passed is False
        assert lock_result.severity == ViolationType.HIGH_RISK

    def test_validate_lock_file_no_lock_file_specified(self):
        """Test validation passes when no lock file is specified (info only)."""
        manifest = DependencyManifest(
            package_name="@acme/pkg",
            version="1.0.0",
            lock_file=None,
        )
        results = self.validator.validate(manifest)
        lock_result = next(r for r in results if r.check == ValidationCheck.LOCK_FILE)
        assert lock_result.passed is True
        assert lock_result.severity == ViolationType.INFO

    def test_validate_net_install_disabled_pass(self):
        """Test validation passes when net-install is disabled."""
        manifest = DependencyManifest(
            package_name="@acme/pkg",
            version="1.0.0",
            net_install_allowed=False,
        )
        results = self.validator.validate(manifest)
        net_result = next(
            r for r in results if r.check == ValidationCheck.NET_INSTALL_DISABLED
        )
        assert net_result.passed is True

    def test_validate_net_install_enabled(self):
        """Test validation fails when net-install is enabled."""
        manifest = DependencyManifest(
            package_name="@acme/pkg",
            version="1.0.0",
            net_install_allowed=True,
        )
        results = self.validator.validate(manifest)
        net_result = next(
            r for r in results if r.check == ValidationCheck.NET_INSTALL_DISABLED
        )
        assert net_result.passed is False
        assert net_result.severity == ViolationType.HIGH_RISK

    def test_validate_all_checks_run(self):
        """Test that all validation checks are run."""
        manifest = DependencyManifest(
            package_name="@acme/pkg",
            version="1.0.0",
            registry="https://private.registry.com",
            lock_file="/nonexistent/lock.yaml",
            net_install_allowed=False,
        )
        results = self.validator.validate(manifest)

        checks_run = {r.check for r in results}
        expected_checks = {
            ValidationCheck.SCOPED_NAME,
            ValidationCheck.PRIVATE_REGISTRY,
            ValidationCheck.LOCK_FILE,
            ValidationCheck.NET_INSTALL_DISABLED,
        }
        assert checks_run == expected_checks

    def test_get_summary_pass(self):
        """Test getting summary when all checks pass."""
        manifest = DependencyManifest(
            package_name="@acme/private-lib",
            version="1.0.0",
            registry="https://private.registry.com",
            lock_file="/tmp/fake-lock.json",
            net_install_allowed=False,
        )
        # Create a fake lock file
        with open(manifest.lock_file, "w") as f:
            f.write('{}')

        summary = self.validator.get_summary(manifest)

        assert summary["passed"] is True
        assert summary["total_checks"] == 4
        assert summary["passed_checks"] == 4
        assert summary["failed_checks"] == 0
        assert summary["score"] == 100

    def test_get_summary_fail(self):
        """Test getting summary when some checks fail."""
        manifest = DependencyManifest(
            package_name="public-lib",  # Unscoped - will fail
            version="1.0.0",
            registry="https://registry.npmjs.org",  # Public - will fail
        )

        summary = self.validator.get_summary(manifest)

        assert summary["passed"] is False
        assert summary["total_checks"] == 4
        assert summary["failed_checks"] == 2  # scoped_name and private_registry
        assert summary["score"] < 100

    def test_get_recommendations(self):
        """Test getting recommendations for failed checks."""
        manifest = DependencyManifest(
            package_name="unscoped-package",  # Will fail scoped check
            version="1.0.0",
            registry="https://public.registry.com",
        )

        recommendations = self.validator.get_recommendations(manifest)

        assert len(recommendations) > 0
        # Should have recommendations for unscoped name
        assert any("scope" in r.lower() for r in recommendations)
        # Should have recommendations for public registry
        assert any("registry" in r.lower() for r in recommendations)

    def test_validate_multiple_manifests(self):
        """Test validating multiple manifests at once."""
        manifests = [
            DependencyManifest(
                package_name="@acme/good",
                version="1.0.0",
                registry="https://private.acme.com",
            ),
            DependencyManifest(
                package_name="bad-pkg",  # Unscoped
                version="2.0.0",
                registry="https://public.registry.com",
            ),
        ]

        results = self.validator.validate_all(manifests)

        assert len(results) == 2
        assert results[0]["passed"] is True
        assert results[1]["passed"] is False

    def test_risk_score_calculation(self):
        """Test overall risk score calculation."""
        # Good manifest
        good_manifest = DependencyManifest(
            package_name="@acme/internal",
            version="1.0.0",
            registry="https://private.acme.com",
            net_install_allowed=False,
        )
        good_score = self.validator.get_risk_score(good_manifest)
        assert good_score == 0

        # Bad manifest with high-risk violations
        bad_manifest = DependencyManifest(
            package_name="public-pkg",
            version="1.0.0",
            registry="https://registry.npmjs.org",
            net_install_allowed=True,
        )
        bad_score = self.validator.get_risk_score(bad_manifest)
        assert bad_score > 0

    def test_severity_mapping(self):
        """Test severity to numeric mapping."""
        assert self.validator._severity_to_score(ViolationType.HIGH_RISK) == 30
        assert self.validator._severity_to_score(ViolationType.MEDIUM_RISK) == 15
        assert self.validator._severity_to_score(ViolationType.LOW_RISK) == 5
        assert self.validator._severity_to_score(ViolationType.INFO) == 0

    def test_private_registry_patterns(self):
        """Test private registry URL patterns."""
        # Should pass
        private_patterns = [
            "https://private-registry.acme.com",
            "https://npm.acme.corp",
            "http://localhost:4873",
            "https://artifactory.internal.com/artifactory/api/npm/npm-local",
        ]
        for url in private_patterns:
            manifest = DependencyManifest(
                package_name="@acme/pkg",
                version="1.0.0",
                registry=url,
            )
            results = self.validator.validate(manifest)
            registry_result = next(
                r for r in results if r.check == ValidationCheck.PRIVATE_REGISTRY
            )
            assert registry_result.passed is True, f"Failed for {url}"

        # Should fail
        public_patterns = [
            "https://registry.npmjs.org",
            "https://registry.yarnpkg.com",
            "https://pypi.org/simple",
        ]
        for url in public_patterns:
            manifest = DependencyManifest(
                package_name="@acme/pkg",
                version="1.0.0",
                registry=url,
            )
            results = self.validator.validate(manifest)
            registry_result = next(
                r for r in results if r.check == ValidationCheck.PRIVATE_REGISTRY
            )
            assert registry_result.passed is False, f"Passed for {url}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
