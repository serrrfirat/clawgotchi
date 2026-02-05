"""Tests for ServiceDependencyChain - orchestrates circuit breakers, timeouts, and fallbacks."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

# Import the module under test
import sys
sys.path.insert(0, '/Users/firatsertgoz/Documents/clawgotchi')
from clawgotchi.resilience.service_chain import ServiceDependencyChain, ServiceConfig, DependencyNode


class TestServiceConfig:
    """Tests for ServiceConfig dataclass."""

    def test_default_config(self):
        """Default configuration has sensible values."""
        config = ServiceConfig(name="test_service")
        assert config.name == "test_service"
        assert config.timeout_ms == 5000
        assert config.fallback_return is None
        assert config.circuit_failure_threshold == 5
        assert config.circuit_reset_timeout_sec == 30

    def test_custom_config(self):
        """Custom configuration values are preserved."""
        config = ServiceConfig(
            name="api_service",
            timeout_ms=1000,
            fallback_return={"status": "degraded"},
            circuit_failure_threshold=3,
            circuit_reset_timeout_sec=60
        )
        assert config.timeout_ms == 1000
        assert config.fallback_return == {"status": "degraded"}
        assert config.circuit_failure_threshold == 3
        assert config.circuit_reset_timeout_sec == 60


class TestDependencyNode:
    """Tests for DependencyNode - represents a single service in the chain."""

    def test_node_initialization(self):
        """Node initializes with config and creates internal circuit breaker."""
        config = ServiceConfig(name="moltbook_api", timeout_ms=3000)
        node = DependencyNode(config)
        assert node.name == "moltbook_api"
        assert config.timeout_ms == 3000

    def test_node_call_success(self):
        """Node executes function successfully."""
        config = ServiceConfig(name="test_service")
        node = DependencyNode(config)

        def sample_func():
            return {"data": "success"}

        result = node.execute(sample_func)
        assert result == {"data": "success"}

    def test_node_call_with_fallback_on_failure(self):
        """Node returns fallback when function raises exception."""
        config = ServiceConfig(name="test_service", fallback_return={"fallback": True})
        node = DependencyNode(config)

        def failing_func():
            raise ConnectionError("Service unavailable")

        result = node.execute(failing_func)
        assert result == {"fallback": True}

    def test_node_call_raises_on_no_fallback(self):
        """Node raises exception when no fallback is configured."""
        config = ServiceConfig(name="test_service")
        node = DependencyNode(config)

        def failing_func():
            raise ConnectionError("Service unavailable")

        with pytest.raises(ConnectionError):
            node.execute(failing_func)


class TestServiceDependencyChain:
    """Tests for ServiceDependencyChain - orchestrates multiple services."""

    def test_chain_initialization(self):
        """Chain initializes with empty dependencies."""
        chain = ServiceDependencyChain()
        assert len(chain._dependencies) == 0

    def test_add_dependency(self):
        """Chain accepts new dependencies."""
        chain = ServiceDependencyChain()
        config = ServiceConfig(name="api_service")
        chain.add(config)

        assert "api_service" in chain._dependencies
        assert len(chain._dependencies) == 1

    def test_add_multiple_dependencies(self):
        """Chain accepts multiple dependencies."""
        chain = ServiceDependencyChain()
        chain.add(ServiceConfig(name="service_a"))
        chain.add(ServiceConfig(name="service_b"))
        chain.add(ServiceConfig(name="service_c"))

        assert len(chain._dependencies) == 3

    def test_set_execution_order(self):
        """Chain respects explicit execution order."""
        chain = ServiceDependencyChain()
        chain.add(ServiceConfig(name="service_a"))
        chain.add(ServiceConfig(name="service_b"))
        chain.add(ServiceConfig(name="service_c"))
        chain.set_order(["service_b", "service_a", "service_c"])

        assert chain._execution_order == ["service_b", "service_a", "service_c"]

    def test_execute_single_service(self):
        """Chain executes a single service successfully."""
        chain = ServiceDependencyChain()
        chain.add(ServiceConfig(name="api_service"))

        def mock_api():
            return {"response": "data"}

        result = chain.execute_service("api_service", mock_api)
        assert result == {"response": "data"}

    def test_execute_chain_all_success(self):
        """Chain executes all services when all succeed."""
        chain = ServiceDependencyChain()
        chain.add(ServiceConfig(name="service_a"))
        chain.add(ServiceConfig(name="service_b"))

        results = chain.execute_chain()
        assert "service_a" in results
        assert "service_b" in results
        assert results["service_a"]["status"] == "success"
        assert results["service_b"]["status"] == "success"

    def test_execute_chain_with_failure_and_fallback(self):
        """Chain handles failure with fallback."""
        chain = ServiceDependencyChain()
        chain.add(ServiceConfig(name="service_a", fallback_return={"status": "fallback_a"}))

        def fail_func():
            raise ConnectionError("fail")

        results = chain.execute_chain([("service_a", fail_func)])
        assert results["service_a"]["status"] == "fallback"

    def test_get_health_status(self):
        """Chain reports health status of all dependencies."""
        chain = ServiceDependencyChain()
        chain.add(ServiceConfig(name="healthy_service"))
        chain.add(ServiceConfig(name="unhealthy_service"))

        status = chain.get_health_status()
        assert "healthy_service" in status
        assert "unhealthy_service" in status


class TestQuickChain:
    """Tests for quick_chain convenience function."""

    def test_quick_chain_creation(self):
        """quick_chain creates chain with multiple services."""
        from clawgotchi.resilience.service_chain import quick_chain

        chain = quick_chain("api", "cache", timeout_ms=3000, fallback={"degraded": True})
        assert "api" in chain
        assert "cache" in chain
        assert len(chain) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
