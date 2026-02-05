"""Tests for the Resilience Registry."""

import pytest
from unittest.mock import patch, MagicMock
from clawgotchi.resilience.registry import (
    ResilienceRegistry,
    get_registry,
    list_all,
    get_summary,
    _registry,
)


class TestResilienceRegistry:
    """Test cases for ResilienceRegistry."""
    
    def test_registry_initialization(self):
        """Registry should initialize and scan components."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            mock_module = MagicMock()
            mock_importlib.import_module.return_value = mock_module
            
            registry = ResilienceRegistry()
            
            # Should have attempted to import each component
            expected_modules = [
                "skills.circuit_breaker.circuit_breaker",
                "skills.timeout_budget.timeout_budget",
                "clawgotchi.resilience.fallback_response",
                "skills.json_escape.json_escape",
                "clawgotchi.resilience.moltbook_config",
                "skills.auto_updater.permission_manifest_scanner",
                "skills.auto_updater.credential_rotation_alerts",
            ]
            assert mock_importlib.import_module.call_count == len(expected_modules)
    
    def test_list_components_filters_unavailable_by_default(self):
        """list_components should exclude unavailable by default."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            mock_module = MagicMock()
            # First import succeeds, second fails, remaining succeed
            successes = [mock_module]  # First succeeds
            failures = [ImportError("test")]  # Second fails
            more_successes = [mock_module] * 5  # Rest succeed
            mock_importlib.import_module.side_effect = successes + failures + more_successes
            
            registry = ResilienceRegistry()
            components = registry.list_components(show_unavailable=False)
            
            # Should only include the ones that succeeded (6)
            assert len(components) == 6
    
    def test_list_components_includes_unavailable_when_requested(self):
        """list_components should include unavailable when requested."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            mock_importlib.import_module.side_effect = ImportError("test")
            
            registry = ResilienceRegistry()
            components = registry.list_components(show_unavailable=True)
            
            # Should include all (even unavailable ones)
            assert len(components) == 7  # Total components defined
    
    def test_get_component_returns_correct_info(self):
        """get_component should return proper component info."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            mock_module = MagicMock()
            mock_importlib.import_module.return_value = mock_module
            
            registry = ResilienceRegistry()
            component = registry.get_component("circuit_breaker")
            
            assert component is not None
            assert component["name"] == "circuit_breaker"
            assert "circuit_breaker" in component["module"]
            assert "description" in component
            assert "last_check" in component
    
    def test_get_component_nonexistent(self):
        """get_component should return None for unknown name."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            registry = ResilienceRegistry()
            component = registry.get_component("nonexistent_component")
            
            assert component is None
    
    def test_get_healthy_count(self):
        """get_healthy_count should return correct count."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            # First 5 succeed, rest fail
            mock_module = MagicMock()
            successes = [mock_module] * 5
            failures = [ImportError("test")] * 2
            mock_importlib.import_module.side_effect = successes + failures
            
            registry = ResilienceRegistry()
            assert registry.get_healthy_count() == 5
    
    def test_get_unhealthy_count(self):
        """get_unhealthy_count should return correct count."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            # First 5 succeed, rest fail
            mock_module = MagicMock()
            successes = [mock_module] * 5
            failures = [ImportError("test")] * 2
            mock_importlib.import_module.side_effect = successes + failures
            
            registry = ResilienceRegistry()
            assert registry.get_unhealthy_count() == 2
    
    def test_get_summary(self):
        """get_summary should return complete summary."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            mock_module = MagicMock()
            mock_importlib.import_module.return_value = mock_module
            
            registry = ResilienceRegistry()
            summary = registry.get_summary()
            
            assert "total_components" in summary
            assert "healthy" in summary
            assert "unhealthy" in summary
            assert "last_refresh" in summary
            assert "uptime_percent" in summary
            assert summary["total_components"] == 7
    
    def test_reload_refreshes_all_components(self):
        """reload should re-scan all components."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            registry = ResilienceRegistry()
            initial_count = mock_importlib.import_module.call_count
            
            registry.reload()
            
            # Should have imported again (total of 2x)
            assert mock_importlib.import_module.call_count == initial_count * 2


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def teardown_method(self):
        """Reset global registry after each test."""
        global _registry
        _registry = None
    
    def test_get_registry_returns_singleton(self):
        """get_registry should return the same instance."""
        reg1 = get_registry()
        reg2 = get_registry()
        
        assert reg1 is reg2
    
    def test_list_all_uses_global_registry(self):
        """list_all should use global registry."""
        global _registry
        _registry = None
        
        # Create a registry and set it as global
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            mock_importlib.import_module.return_value = MagicMock()
            _registry = ResilienceRegistry()
            
            # list_all should use the global registry
            result = list_all()
            
            # Should have used global registry (no new registry created)
            # Since we set _registry before calling list_all, it should use it
            assert _registry is not None
            assert len(result) == 7
    
    def test_get_summary_uses_global_registry(self):
        """get_summary should use global registry."""
        global _registry
        _registry = None
        
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            mock_importlib.import_module.return_value = MagicMock()
            result = get_summary()
            
            assert "total_components" in result


class TestComponentDiscovery:
    """Test component discovery and function extraction."""
    
    def test_functions_are_discovered(self):
        """Registry should extract function names from modules."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            mock_module = MagicMock()
            mock_importlib.import_module.return_value = mock_module
            
            with patch('clawgotchi.resilience.registry.inspect') as mock_inspect:
                mock_func1 = MagicMock(__name__="test_func1")
                mock_func2 = MagicMock(__name__="test_func2")
                mock_inspect.getmembers.return_value = [
                    ("test_func1", mock_func1),
                    ("test_func2", mock_func2),
                    ("_private_func", MagicMock(__name__="_private_func")),
                ]
                
                registry = ResilienceRegistry()
                component = registry.get_component("circuit_breaker")
                
                # Should include public functions only
                assert "test_func1" in component["functions"]
                assert "test_func2" in component["functions"]
                assert "_private_func" not in component["functions"]
    
    def test_error_is_recorded_on_import_failure(self):
        """Import errors should be recorded in component info."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            mock_importlib.import_module.side_effect = ImportError("Module not found")
            
            registry = ResilienceRegistry()
            component = registry.get_component("circuit_breaker")
            
            assert component["available"] is False
            assert "Module not found" in component["error"]
    
    def test_last_check_is_iso_format(self):
        """last_check should be an ISO timestamp."""
        with patch('clawgotchi.resilience.registry.importlib') as mock_importlib:
            registry = ResilienceRegistry()
            component = registry.get_component("circuit_breaker")
            
            # Should contain date and time
            assert "T" in component["last_check"]  # ISO format
            assert ":" in component["last_check"]  # Time separator
