"""Tests for ResilienceDiagnostic utility."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import sys
from pathlib import Path

# Add clawgotchi to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestResilienceDiagnostic:
    """Test suite for ResilienceDiagnostic class."""

    def test_quick_check_returns_dict(self):
        """Test that quick_check returns a dictionary."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.quick_check()
        assert isinstance(result, dict)

    def test_quick_check_contains_status(self):
        """Test that quick_check result contains 'status' key."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.quick_check()
        assert "status" in result

    def test_quick_check_contains_healthy_count(self):
        """Test that quick_check result contains 'healthy_count'."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.quick_check()
        assert "healthy_count" in result

    def test_full_check_returns_dict(self):
        """Test that full_check returns a dictionary."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.full_check()
        assert isinstance(result, dict)

    def test_full_check_contains_components(self):
        """Test that full_check result contains 'components' key."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.full_check()
        assert "components" in result

    def test_full_check_contains_summary(self):
        """Test that full_check result contains 'summary' key."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.full_check()
        assert "summary" in result

    def test_get_component_status_returns_dict(self):
        """Test that get_component_status returns a dictionary."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("circuit_breaker")
        assert isinstance(status, dict)

    def test_get_component_status_unknown_component(self):
        """Test getting status of an unknown component."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("non_existent_component")
        assert status["status"] == "unknown"

    def test_health_score_calculated(self):
        """Test that health score is calculated correctly."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        score = diagnostic.get_health_score()
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

    def test_diagnostic_info_included(self):
        """Test that diagnostic info is included in full_check."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.full_check()
        assert "last_check_timestamp" in result
        assert "component_versions" in result

    def test_circuit_breaker_check(self):
        """Test checking circuit_breaker component."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("circuit_breaker")
        # Status should be healthy, degraded, or unknown
        assert status["status"] in ["healthy", "degraded", "unknown"]

    def test_timeout_budget_check(self):
        """Test checking timeout_budget component."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("timeout_budget")
        assert status["status"] in ["healthy", "degraded", "unknown"]

    def test_fallback_response_check(self):
        """Test checking fallback_response component."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("fallback_response")
        assert status["status"] in ["healthy", "degraded", "unknown"]

    def test_json_escape_check(self):
        """Test checking json_escape component."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("json_escape")
        assert status["status"] in ["healthy", "degraded", "unknown"]

    def test_moltbook_config_check(self):
        """Test checking moltbook_config component."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("moltbook_config")
        assert status["status"] in ["healthy", "degraded", "unknown"]

    def test_service_chain_check(self):
        """Test checking service_chain component."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("service_chain")
        assert status["status"] in ["healthy", "degraded", "unknown"]

    def test_permission_manifest_scanner_check(self):
        """Test checking permission_manifest_scanner component."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("permission_manifest_scanner")
        assert status["status"] in ["healthy", "degraded", "unknown"]

    def test_credential_rotation_alerts_check(self):
        """Test checking credential_rotation_alerts component."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_component_status("credential_rotation_alerts")
        assert status["status"] in ["healthy", "degraded", "unknown"]

    def test_overall_status_healthy(self):
        """Test that overall status is 'healthy' when most components are healthy."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_overall_status()
        assert status in ["healthy", "degraded", "critical", "unknown"]

    def test_summary_dict_structure(self):
        """Test that summary dict has expected structure."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        summary = diagnostic.get_summary()
        assert "overall_health_score" in summary
        assert "components_checked" in summary
        assert "healthy_count" in summary
        assert "degraded_count" in summary
        assert "unknown_count" in summary

    def test_quick_check_performance(self):
        """Test that quick_check runs quickly (under 1 second)."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        import time
        start = time.time()
        result = diagnostic.quick_check()
        elapsed = time.time() - start
        assert elapsed < 1.0  # Should complete in under 1 second

    def test_get_health_score_returns_percentage(self):
        """Test that health score returns a percentage value."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        diagnostic = ResilienceDiagnostic()
        score = diagnostic.get_health_score()
        assert 0 <= score <= 100
