"""
Tests for Resilience Health Diagnostic Utility.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import importlib


class TestResilienceDiagnostic:
    """Tests for the ResilienceDiagnostic class."""
    
    def test_module_paths_exist(self):
        """Test that required module paths are defined."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        # All components should have module paths
        for component in ResilienceDiagnostic.COMPONENTS:
            if component in ResilienceDiagnostic.MODULE_PATHS:
                assert True
            else:
                pytest.fail(f"Component {component} has no module path defined")
    
    def test_quick_check_returns_dict(self):
        """Test that quick_check returns a dictionary."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.quick_check()
        
        assert isinstance(result, dict)
        assert "status" in result
        assert "healthy_count" in result
        assert "total_count" in result
        assert "timestamp" in result
    
    def test_quick_check_status_values(self):
        """Test that quick_check returns valid status values."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.quick_check()
        
        valid_statuses = ["healthy", "degraded", "critical"]
        assert result["status"] in valid_statuses
        assert result["healthy_count"] >= 0
        assert result["total_count"] > 0
    
    def test_full_check_returns_dict(self):
        """Test that full_check returns a dictionary with required keys."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.full_check()
        
        assert isinstance(result, dict)
        assert "components" in result
        assert "summary" in result
        assert "last_check_timestamp" in result
    
    def test_full_check_has_summary(self):
        """Test that full_check summary has required fields."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.full_check()
        
        summary = result["summary"]
        assert "overall_health_score" in summary
        assert "components_checked" in summary
        assert "healthy_count" in summary
        assert "degraded_count" in summary
    
    def test_get_health_score_returns_float(self):
        """Test that get_health_score returns a float between 0 and 100."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        score = diagnostic.get_health_score()
        
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100
    
    def test_get_overall_status_returns_string(self):
        """Test that get_overall_status returns a valid status string."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        status = diagnostic.get_overall_status()
        
        valid_statuses = ["healthy", "degraded", "critical", "unknown"]
        assert status in valid_statuses
    
    def test_get_component_status_unknown_component(self):
        """Test that get_component_status returns unknown for invalid components."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.get_component_status("nonexistent_component")
        
        assert result["status"] == "unknown"
        assert result["available"] is False
    
    def test_get_summary_returns_dict(self):
        """Test that get_summary returns a dictionary with summary statistics."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        summary = diagnostic.get_summary()
        
        assert isinstance(summary, dict)
        assert "overall_health_score" in summary
        assert "components_checked" in summary
        assert "healthy_count" in summary
        assert "last_check" in summary
    
    def test_components_list_not_empty(self):
        """Test that COMPONENTS list is not empty."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        assert len(ResilienceDiagnostic.COMPONENTS) > 0
    
    def test_quick_health_check_function(self):
        """Test the quick_health_check convenience function."""
        from clawgotchi.resilience_diagnostic import quick_health_check
        
        result = quick_health_check()
        
        assert isinstance(result, dict)
        assert "status" in result
        assert "healthy_count" in result
    
    def test_create_diagnostic_factory(self):
        """Test the create_diagnostic factory function."""
        from clawgotchi.resilience_diagnostic import create_diagnostic
        
        diagnostic = create_diagnostic()
        
        assert diagnostic is not None
        assert hasattr(diagnostic, 'quick_check')
        assert hasattr(diagnostic, 'full_check')
    
    def test_initialization_sets_last_check(self):
        """Test that initialization sets the last_check timestamp."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        before = datetime.utcnow()
        diagnostic = ResilienceDiagnostic()
        after = datetime.utcnow()
        
        assert diagnostic._last_check is not None
        assert before <= diagnostic._last_check <= after
    
    def test_refresh_cache_populates_component_cache(self):
        """Test that _refresh_cache populates the component cache."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        diagnostic._refresh_cache()
        
        assert len(diagnostic._component_cache) > 0
        for component in ResilienceDiagnostic.COMPONENTS:
            assert component in diagnostic._component_cache
    
    def test_check_component_returns_dict(self):
        """Test that _check_component returns a properly structured dict."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        
        for component in ResilienceDiagnostic.COMPONENTS:
            result = diagnostic._check_component(component)
            
            assert "component" in result
            assert "status" in result
            assert "available" in result
            assert result["component"] == component


class TestResilienceDiagnosticIntegration:
    """Integration tests for ResilienceDiagnostic."""
    
    def test_components_attribute_is_list(self):
        """Test that COMPONENTS is a list."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        assert isinstance(ResilienceDiagnostic.COMPONENTS, list)
    
    def test_module_paths_attribute_is_dict(self):
        """Test that MODULE_PATHS is a dictionary."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        assert isinstance(ResilienceDiagnostic.MODULE_PATHS, dict)
    
    def test_timestamp_format(self):
        """Test that timestamp is in ISO format."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        result = diagnostic.quick_check()
        
        if result["timestamp"]:
            parsed = datetime.fromisoformat(result["timestamp"])
            assert parsed is not None
    
    def test_health_score_calculation(self):
        """Test that health score is calculated correctly."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        score = diagnostic.get_health_score()
        summary = diagnostic.get_summary()
        
        assert abs(score - summary["overall_health_score"]) < 1
    
    def test_components_and_summary_consistency(self):
        """Test that components and summary are consistent."""
        from clawgotchi.resilience_diagnostic import ResilienceDiagnostic
        
        diagnostic = ResilienceDiagnostic()
        full_result = diagnostic.full_check()
        
        components = full_result["components"]
        summary = full_result["summary"]
        
        healthy = sum(1 for c in components.values() if c["status"] == "healthy")
        degraded = sum(1 for c in components.values() if c["status"] == "degraded")
        
        assert healthy == summary["healthy_count"]
        assert degraded == summary["degraded_count"]
        assert healthy + degraded <= summary["components_checked"]
