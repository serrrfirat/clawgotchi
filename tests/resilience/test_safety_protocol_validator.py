"""
Tests for Safety Protocol Validator.
"""

import pytest
from clawgotchi.resilience.safety_protocol_validator import (
    SafetyCategory,
    SafetyLevel,
    SafetyCheck,
    SafetyReport,
    SafetyProtocolValidator,
    create_safety_report
)


class TestSafetyCheck:
    """Tests for SafetyCheck dataclass."""
    
    def test_safety_check_creation(self):
        check = SafetyCheck(
            category=SafetyCategory.HUMAN_IN_LOOP,
            check_name="hil_enabled",
            passed=True,
            severity=SafetyLevel.RECOMMENDED,
            message="HIL is enabled"
        )
        assert check.category == SafetyCategory.HUMAN_IN_LOOP
        assert check.check_name == "hil_enabled"
        assert check.passed is True
        assert check.severity == SafetyLevel.RECOMMENDED
    
    def test_safety_check_with_recommendation(self):
        check = SafetyCheck(
            category=SafetyCategory.ROLLBACK,
            check_name="rollback_enabled",
            passed=False,
            severity=SafetyLevel.REQUIRED,
            message="Rollback not configured",
            recommendation="Enable rollback in config"
        )
        assert check.recommendation == "Enable rollback in config"


class TestSafetyReport:
    """Tests for SafetyReport dataclass."""
    
    def test_empty_report_score(self):
        report = SafetyReport()
        assert report.calculate_score() == 0
    
    def test_all_passed_score(self):
        report = SafetyReport()
        report.checks = [
            SafetyCheck(SafetyCategory.HUMAN_IN_LOOP, "a", True, SafetyLevel.REQUIRED, "msg"),
            SafetyCheck(SafetyCategory.ROLLBACK, "b", True, SafetyLevel.REQUIRED, "msg"),
            SafetyCheck(SafetyCategory.LOGGING, "c", True, SafetyLevel.REQUIRED, "msg"),
        ]
        assert report.calculate_score() == 100
    
    def test_half_passed_score(self):
        report = SafetyReport()
        report.checks = [
            SafetyCheck(SafetyCategory.HUMAN_IN_LOOP, "a", True, SafetyLevel.REQUIRED, "msg"),
            SafetyCheck(SafetyCategory.ROLLBACK, "b", False, SafetyLevel.REQUIRED, "msg"),
            SafetyCheck(SafetyCategory.LOGGING, "c", True, SafetyLevel.REQUIRED, "msg"),
        ]
        # Two passed, one failed with REQUIRED (weight 3) = 2/3 = 67%
        score = report.calculate_score()
        assert score >= 60 and score <= 70
    
    def test_status_excellent(self):
        report = SafetyReport()
        report.checks = [
            SafetyCheck(SafetyCategory.HUMAN_IN_LOOP, "a", True, SafetyLevel.RECOMMENDED, "msg"),
            SafetyCheck(SafetyCategory.ROLLBACK, "b", True, SafetyLevel.RECOMMENDED, "msg"),
            SafetyCheck(SafetyCategory.LOGGING, "c", True, SafetyLevel.RECOMMENDED, "msg"),
        ]
        assert report.get_status() == "excellent"
    
    def test_status_critical(self):
        report = SafetyReport()
        report.checks = [
            SafetyCheck(SafetyCategory.HUMAN_IN_LOOP, "a", False, SafetyLevel.CRITICAL, "msg"),
            SafetyCheck(SafetyCategory.ROLLBACK, "b", False, SafetyLevel.CRITICAL, "msg"),
            SafetyCheck(SafetyCategory.LOGGING, "c", False, SafetyLevel.CRITICAL, "msg"),
        ]
        assert report.get_status() == "critical"
    
    def test_to_dict(self):
        report = SafetyReport()
        report.checks = [
            SafetyCheck(SafetyCategory.HUMAN_IN_LOOP, "hil", True, SafetyLevel.REQUIRED, "HIL OK"),
        ]
        result = report.to_dict()
        assert "checks" in result
        assert "overall_score" in result
        assert "overall_status" in result
        assert result["checks"][0]["check_name"] == "hil"


class TestSafetyProtocolValidator:
    """Tests for SafetyProtocolValidator class."""
    
    def test_hil_not_required_and_not_enabled(self):
        validator = SafetyProtocolValidator(hil_required=False)
        check = validator.validate_human_in_loop({"enabled": False})
        assert check.passed is True
    
    def test_hil_required_but_not_enabled(self):
        validator = SafetyProtocolValidator(hil_required=True)
        check = validator.validate_human_in_loop({"enabled": False})
        assert check.passed is False
        assert check.severity == SafetyLevel.REQUIRED
        assert "required" in check.message.lower()
    
    def test_hil_enabled(self):
        validator = SafetyProtocolValidator(hil_required=True)
        check = validator.validate_human_in_loop({"enabled": True, "stages": ["init", "approval"]})
        assert check.passed is True
    
    def test_hil_invalid_stages(self):
        validator = SafetyProtocolValidator(hil_required=True)
        check = validator.validate_human_in_loop({"enabled": True, "stages": ["invalid_stage"]})
        assert check.passed is False
        assert "Invalid HIL stages" in check.message
    
    def test_hil_valid_stages(self):
        validator = SafetyProtocolValidator(hil_required=True)
        check = validator.validate_human_in_loop(
            {"enabled": True, "stages": ["init", "approval", "execution"]}
        )
        assert check.passed is True
    
    def test_rollback_not_required_and_not_enabled(self):
        validator = SafetyProtocolValidator(rollback_required=False)
        check = validator.validate_rollback({"enabled": False})
        assert check.passed is True
    
    def test_rollback_required_but_not_enabled(self):
        validator = SafetyProtocolValidator(rollback_required=True)
        check = validator.validate_rollback({"enabled": False})
        assert check.passed is False
        assert check.severity == SafetyLevel.REQUIRED
    
    def test_rollback_enabled(self):
        validator = SafetyProtocolValidator(rollback_required=True)
        check = validator.validate_rollback({
            "enabled": True, 
            "types": ["full", "checkpoint"],
            "escape_hatch": {"enabled": True}
        })
        assert check.passed is True
    
    def test_rollback_invalid_types(self):
        validator = SafetyProtocolValidator(rollback_required=True)
        check = validator.validate_rollback({"enabled": True, "types": ["invalid_type"]})
        assert check.passed is False
        assert "Invalid rollback types" in check.message
    
    def test_rollback_valid_types(self):
        validator = SafetyProtocolValidator(rollback_required=True)
        check = validator.validate_rollback({
            "enabled": True, 
            "types": ["full", "partial"],
            "escape_hatch": {"enabled": True}
        })
        assert check.passed is True
    
    def test_rollback_no_escape_hatch(self):
        validator = SafetyProtocolValidator(rollback_required=True)
        check = validator.validate_rollback({"enabled": True, "types": ["full"]})
        assert check.passed is False
        assert "escape hatch" in check.message.lower()
    
    def test_rollback_with_escape_hatch(self):
        validator = SafetyProtocolValidator(rollback_required=True)
        check = validator.validate_rollback({
            "enabled": True,
            "types": ["full"],
            "escape_hatch": {"enabled": True, "timeout": 30}
        })
        assert check.passed is True
    
    def test_logging_not_required_and_not_enabled(self):
        validator = SafetyProtocolValidator(logging_required=False)
        check = validator.validate_logging({"enabled": False})
        assert check.passed is True
    
    def test_logging_required_but_not_enabled(self):
        validator = SafetyProtocolValidator(logging_required=True)
        check = validator.validate_logging({"enabled": False})
        assert check.passed is False
        assert check.severity == SafetyLevel.REQUIRED
    
    def test_logging_enabled_with_all_types(self):
        validator = SafetyProtocolValidator(logging_required=True)
        check = validator.validate_logging({
            "enabled": True,
            "types": ["operation", "error", "audit"],
            "retention_days": 30
        })
        assert check.passed is True
    
    def test_logging_missing_types(self):
        validator = SafetyProtocolValidator(logging_required=True)
        check = validator.validate_logging({
            "enabled": True,
            "types": ["operation"],
            "retention_days": 30
        })
        assert check.passed is False
        assert "Missing log types" in check.message
    
    def test_logging_low_retention(self):
        validator = SafetyProtocolValidator(logging_required=True)
        check = validator.validate_logging({
            "enabled": True,
            "types": ["operation", "error", "audit"],
            "retention_days": 3
        })
        assert check.passed is False
        assert "retention" in check.message.lower()
    
    def test_logging_good_retention(self):
        validator = SafetyProtocolValidator(logging_required=True)
        check = validator.validate_logging({
            "enabled": True,
            "types": ["operation", "error", "audit"],
            "retention_days": 14
        })
        assert check.passed is True
    
    def test_verification_valid_levels(self):
        validator = SafetyProtocolValidator()
        check = validator.validate_verification({
            "levels": ["pre", "post", "manual"]
        })
        assert check.passed is True
    
    def test_verification_invalid_levels(self):
        validator = SafetyProtocolValidator()
        check = validator.validate_verification({
            "levels": ["invalid_level"]
        })
        assert check.passed is False
    
    def test_verification_critical_without_external(self):
        validator = SafetyProtocolValidator()
        check = validator.validate_verification({
            "operations": ["critical"],
            "levels": ["pre", "post"]
        })
        assert check.passed is False
        assert "external verification" in check.message.lower()
    
    def test_verification_critical_with_external(self):
        validator = SafetyProtocolValidator()
        check = validator.validate_verification({
            "operations": ["critical"],
            "levels": ["pre", "post", "external"]
        })
        assert check.passed is True
    
    def test_validate_protocol_complete(self):
        validator = SafetyProtocolValidator()
        report = validator.validate_protocol(
            hil_config={"enabled": True, "stages": ["init"]},
            rollback_config={"enabled": True, "types": ["full"], "escape_hatch": {"enabled": True}},
            logging_config={"enabled": True, "types": ["operation", "error", "audit"], "retention_days": 30},
            verification_config={"levels": ["pre", "post"]}
        )
        assert len(report.checks) == 4
        assert report.calculate_score() == 100
        assert report.get_status() == "excellent"
    
    def test_validate_protocol_empty(self):
        validator = SafetyProtocolValidator(
            hil_required=False, 
            rollback_required=False,
            logging_required=False
        )
        report = validator.validate_protocol()
        # All defaults pass with all requirements disabled
        assert report.calculate_score() == 100
    
    def test_quick_check_all_good(self):
        validator = SafetyProtocolValidator()
        result = validator.quick_check({
            "human_in_loop": {"enabled": True},
            "rollback": {"enabled": True},
            "logging": {"enabled": True}
        })
        assert result["has_hil"] is True
        assert result["has_rollback"] is True
        assert result["has_logging"] is True
        assert result["score"] == 100
        assert result["status"] == "good"
    
    def test_quick_check_all_missing(self):
        validator = SafetyProtocolValidator()
        result = validator.quick_check({
            "human_in_loop": {"enabled": False},
            "rollback": {"enabled": False},
            "logging": {"enabled": False}
        })
        assert result["has_hil"] is False
        assert result["has_rollback"] is False
        assert result["has_logging"] is False
        assert result["score"] == 0
        assert result["status"] == "warning"


class TestCreateSafetyReport:
    """Tests for create_safety_report helper."""
    
    def test_create_safety_report_helper(self):
        report = create_safety_report(
            hil_config={"enabled": True, "stages": ["init"]},
            rollback_config={"enabled": True, "types": ["full"]},
            logging_config={"enabled": True, "types": ["operation"], "retention_days": 30},
            verification_config={"levels": ["pre"]}
        )
        assert isinstance(report, SafetyReport)
        assert len(report.checks) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
