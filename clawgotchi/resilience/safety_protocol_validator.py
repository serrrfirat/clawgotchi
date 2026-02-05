"""
Safety Protocol Validator for Agent Operations.

Validates safety protocols for agent automation: human-in-the-loop presence,
rollback/escape hatch definitions, and logging requirements.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json
from pathlib import Path


class SafetyCategory(Enum):
    HUMAN_IN_LOOP = "human_in_loop"
    ROLLBACK = "rollback"
    LOGGING = "logging"
    ESCAPE_HATCH = "escape_hatch"
    VERIFICATION = "verification"


class SafetyLevel(Enum):
    """Safety protocol strictness levels."""
    NONE = 0
    RECOMMENDED = 1
    REQUIRED = 2
    CRITICAL = 3


@dataclass
class SafetyCheck:
    """Individual safety check result."""
    category: SafetyCategory
    check_name: str
    passed: bool
    severity: SafetyLevel
    message: str
    recommendation: Optional[str] = None


@dataclass 
class SafetyReport:
    """Complete safety validation report."""
    checks: list[SafetyCheck] = field(default_factory=list)
    overall_score: int = 0
    overall_status: str = "unknown"
    validated_at: str = ""
    
    def add_check(self, check: SafetyCheck) -> None:
        self.checks.append(check)
    
    def calculate_score(self) -> int:
        """Calculate overall safety score (0-100)."""
        if not self.checks:
            return 0
        
        total_weight = 0
        weighted_score = 0
        
        for check in self.checks:
            weight = check.severity.value + 1  # Scale 1-4
            total_weight += weight
            if check.passed:
                weighted_score += weight
        
        return int((weighted_score / total_weight) * 100) if total_weight > 0 else 0
    
    def get_status(self) -> str:
        """Get overall safety status."""
        score = self.calculate_score()
        if score >= 90:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 50:
            return "acceptable"
        elif score >= 30:
            return "warning"
        else:
            return "critical"
    
    def to_dict(self) -> dict:
        return {
            "checks": [c.__dict__ for c in self.checks],
            "overall_score": self.calculate_score(),
            "overall_status": self.get_status(),
            "validated_at": self.validated_at
        }


class SafetyProtocolValidator:
    """Validates safety protocols for agent operations."""
    
    # Default thresholds
    DEFAULT_HIL_REQUIRED = False
    DEFAULT_ROLLBACK_REQUIRED = True
    DEFAULT_LOGGING_REQUIRED = True
    
    def __init__(
        self,
        hil_required: bool = DEFAULT_HIL_REQUIRED,
        rollback_required: bool = DEFAULT_ROLLBACK_REQUIRED,
        logging_required: bool = DEFAULT_LOGGING_REQUIRED
    ):
        self.hil_required = hil_required
        self.rollback_required = rollback_required
        self.logging_required = logging_required
    
    def validate_human_in_loop(
        self,
        hil_config: dict,
        context: str = "general"
    ) -> SafetyCheck:
        """Validate human-in-the-loop configuration."""
        category = SafetyCategory.HUMAN_IN_LOOP
        
        # Check if human-in-loop is configured
        hil_present = hil_config.get("enabled", False)
        hil_stages = hil_config.get("stages", [])
        
        if self.hil_required and not hil_present:
            return SafetyCheck(
                category=category,
                check_name="hil_enabled",
                passed=False,
                severity=SafetyLevel.REQUIRED,
                message="Human-in-the-loop is required but not configured",
                recommendation="Set hil_config['enabled'] = true and specify stages"
            )
        
        # Validate stages if present
        valid_stages = ["init", "approval", "execution", "review", "rollback"]
        if hil_stages:
            invalid_stages = [s for s in hil_stages if s not in valid_stages]
            if invalid_stages:
                return SafetyCheck(
                    category=category,
                    check_name="hil_stages",
                    passed=False,
                    severity=SafetyLevel.RECOMMENDED,
                    message=f"Invalid HIL stages: {invalid_stages}",
                    recommendation=f"Use valid stages: {valid_stages}"
                )
        
        return SafetyCheck(
            category=category,
            check_name="hil_config",
            passed=True,
            severity=SafetyLevel.RECOMMENDED,
            message=f"HIL {'enabled' if hil_present else 'not required'} for {context}",
            recommendation=None
        )
    
    def validate_rollback(self, rollback_config: dict) -> SafetyCheck:
        """Validate rollback/escape hatch configuration."""
        category = SafetyCategory.ROLLBACK
        
        # Check for rollback mechanism
        has_rollback = rollback_config.get("enabled", False)
        rollback_types = rollback_config.get("types", [])
        
        if self.rollback_required and not has_rollback:
            return SafetyCheck(
                category=category,
                check_name="rollback_enabled",
                passed=False,
                severity=SafetyLevel.REQUIRED,
                message="Rollback mechanism is required but not configured",
                recommendation="Set rollback_config['enabled'] = true and specify types"
            )
        
        # Validate rollback types
        valid_types = ["full", "partial", "checkpoint", "emergency"]
        if rollback_types:
            invalid_types = [t for t in rollback_types if t not in valid_types]
            if invalid_types:
                return SafetyCheck(
                    category=category,
                    check_name="rollback_types",
                    passed=False,
                    severity=SafetyLevel.RECOMMENDED,
                    message=f"Invalid rollback types: {invalid_types}",
                    recommendation=f"Use valid types: {valid_types}"
                )
        
        # Check for escape hatch (only if rollback is enabled)
        has_escape_hatch = rollback_config.get("escape_hatch", {}).get("enabled", False)
        if has_rollback and not has_escape_hatch:
            return SafetyCheck(
                category=category,
                check_name="escape_hatch",
                passed=False,
                severity=SafetyLevel.RECOMMENDED,
                message="No emergency escape hatch configured",
                recommendation="Add escape_hatch with timeout and abort capability"
            )
        
        return SafetyCheck(
            category=category,
            check_name="rollback_config",
            passed=True,
            severity=SafetyLevel.REQUIRED,
            message=f"Rollback configured with types: {rollback_types or ['default']}",
            recommendation=None
        )
    
    def validate_logging(self, logging_config: dict) -> SafetyCheck:
        """Validate logging configuration."""
        category = SafetyCategory.LOGGING
        
        # Check for logging
        logging_enabled = logging_config.get("enabled", True)
        log_types = logging_config.get("types", [])
        log_retention = logging_config.get("retention_days", 0)
        
        if self.logging_required and not logging_enabled:
            return SafetyCheck(
                category=category,
                check_name="logging_enabled",
                passed=False,
                severity=SafetyLevel.REQUIRED,
                message="Logging is required but disabled",
                recommendation="Set logging_config['enabled'] = true"
            )
        
        # Only do deep checks if logging is explicitly enabled AND config is provided
        if logging_enabled and logging_config:
            # Check log types
            required_types = {"operation", "error", "audit"}
            if log_types:
                missing_types = required_types - set(log_types)
                if missing_types:
                    return SafetyCheck(
                        category=category,
                        check_name="log_types",
                        passed=False,
                        severity=SafetyLevel.RECOMMENDED,
                        message=f"Missing log types: {missing_types}",
                        recommendation=f"Include: {required_types}"
                    )
            
            # Check retention (only if explicitly provided)
            if log_retention > 0 and log_retention < 7:
                return SafetyCheck(
                    category=category,
                    check_name="log_retention",
                    passed=False,
                    severity=SafetyLevel.RECOMMENDED,
                    message=f"Log retention {log_retention} days is below recommended 7 days",
                    recommendation="Increase retention_days to at least 7"
                )
        
        return SafetyCheck(
            category=category,
            check_name="logging_config",
            passed=True,
            severity=SafetyLevel.REQUIRED,
            message=f"Logging enabled with {len(log_types)} types, {log_retention} day retention",
            recommendation=None
        )
    
    def validate_verification(self, verification_config: dict) -> SafetyCheck:
        """Validate verification requirements."""
        category = SafetyCategory.VERIFICATION
        
        # Check verification levels
        verification_levels = verification_config.get("levels", [])
        auto_verified = verification_config.get("auto_verified", [])
        
        valid_levels = ["pre", "post", "manual", "external"]
        if verification_levels:
            invalid_levels = [l for l in verification_levels if l not in valid_levels]
            if invalid_levels:
                return SafetyCheck(
                    category=category,
                    check_name="verification_levels",
                    passed=False,
                    severity=SafetyLevel.RECOMMENDED,
                    message=f"Invalid verification levels: {invalid_levels}",
                    recommendation=f"Use valid levels: {valid_levels}"
                )
        
        # Check for external verification in critical operations
        if "critical" in verification_config.get("operations", []):
            if "external" not in verification_levels:
                return SafetyCheck(
                    category=category,
                    check_name="external_verification",
                    passed=False,
                    severity=SafetyLevel.CRITICAL,
                    message="Critical operations lack external verification",
                    recommendation="Add 'external' to verification levels for critical ops"
                )
        
        return SafetyCheck(
            category=category,
            check_name="verification_config",
            passed=True,
            severity=SafetyLevel.RECOMMENDED,
            message=f"Verification configured with {len(verification_levels)} levels",
            recommendation=None
        )
    
    def validate_protocol(
        self,
        hil_config: Optional[dict] = None,
        rollback_config: Optional[dict] = None,
        logging_config: Optional[dict] = None,
        verification_config: Optional[dict] = None,
        context: str = "general"
    ) -> SafetyReport:
        """Run complete safety protocol validation."""
        from datetime import datetime
        
        report = SafetyReport()
        report.validated_at = datetime.utcnow().isoformat()
        
        # Run all checks
        hil_result = self.validate_human_in_loop(hil_config or {}, context)
        report.add_check(hil_result)
        
        rollback_result = self.validate_rollback(rollback_config or {})
        report.add_check(rollback_result)
        
        logging_result = self.validate_logging(logging_config or {})
        report.add_check(logging_result)
        
        verification_result = self.validate_verification(verification_config or {})
        report.add_check(verification_result)
        
        return report
    
    def quick_check(self, config: dict) -> dict:
        """Fast safety check for monitoring."""
        has_hil = config.get("human_in_loop", {}).get("enabled", False)
        has_rollback = config.get("rollback", {}).get("enabled", False)
        has_logging = config.get("logging", {}).get("enabled", True)
        
        passed_checks = sum([has_hil, has_rollback, has_logging])
        score = int((passed_checks / 3) * 100)
        
        return {
            "has_hil": has_hil,
            "has_rollback": has_rollback,
            "has_logging": has_logging,
            "score": score,
            "status": "good" if score >= 70 else "warning"
        }


def create_safety_report(
    hil_config: Optional[dict] = None,
    rollback_config: Optional[dict] = None,
    logging_config: Optional[dict] = None,
    verification_config: Optional[dict] = None
) -> SafetyReport:
    """Helper to create a complete safety report."""
    validator = SafetyProtocolValidator()
    return validator.validate_protocol(
        hil_config=hil_config,
        rollback_config=rollback_config,
        logging_config=logging_config,
        verification_config=verification_config
    )
