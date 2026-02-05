"""
Tests for Service Chain Validator
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestServiceChainValidator:
    """Test suite for ServiceChainValidator."""
    
    def test_validator_initializes_empty(self):
        """Validator starts with empty component registry."""
        from service_chain_validator import ServiceChainValidator
        validator = ServiceChainValidator()
        assert validator.get_registered_components() == {}
        assert validator.get_chain_status()["valid"] == True
        assert len(validator.get_chain_status()["components"]) == 0
    
    def test_register_circuit_breaker(self):
        """Circuit breaker can be registered as a component."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.CLOSED
        mock_cb.failure_count = 0
        mock_cb.name = "TestAPI"
        
        validator.register_component("circuit_breaker", mock_cb)
        
        components = validator.get_registered_components()
        assert "circuit_breaker" in components
        assert components["circuit_breaker"]["name"] == "TestAPI"
    
    def test_register_fallback_generator(self):
        """Fallback generator can be registered."""
        from service_chain_validator import ServiceChainValidator
        
        validator = ServiceChainValidator()
        mock_fallback = Mock()
        mock_fallback.get_fallback = Mock(return_value={"status": "cached"})
        mock_fallback.strategy = "RETURN_CACHED"
        
        validator.register_component("fallback_response", mock_fallback)
        
        components = validator.get_registered_components()
        assert "fallback_response" in components
    
    def test_register_json_escape(self):
        """JSON escape utility can be registered."""
        from service_chain_validator import ServiceChainValidator
        
        validator = ServiceChainValidator()
        mock_escape = Mock()
        mock_escape.escape_for_moltbook = Mock(return_value="safe string")
        
        validator.register_component("json_escape", mock_escape)
        
        components = validator.get_registered_components()
        assert "json_escape" in components
    
    def test_validate_chain_with_all_components(self):
        """Full chain validation with all resilience components."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        
        # Mock circuit breaker
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.CLOSED
        mock_cb.failure_count = 0
        mock_cb.name = "TestAPI"
        
        # Mock fallback
        mock_fallback = Mock()
        mock_fallback.get_fallback = Mock(return_value={"status": "default"})
        mock_fallback.strategy = "RETURN_DEFAULT"
        
        # Mock JSON escape
        mock_escape = Mock()
        mock_escape.escape_for_moltbook = Mock(return_value="escaped")
        
        validator.register_component("circuit_breaker", mock_cb)
        validator.register_component("fallback_response", mock_fallback)
        validator.register_component("json_escape", mock_escape)
        
        status = validator.get_chain_status()
        assert status["valid"] == True
        assert len(status["components"]) == 3
        assert status["health_score"] == 100
    
    def test_validate_chain_open_circuit_breaker(self):
        """Validation fails when circuit breaker is open."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.OPEN
        mock_cb.failure_count = 5
        mock_cb.name = "DeadAPI"
        
        validator.register_component("circuit_breaker", mock_cb)
        
        status = validator.get_chain_status()
        assert status["valid"] == False
        assert status["health_score"] < 100
    
    def test_validate_chain_missing_dependencies(self):
        """Validation reports missing dependencies."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.CLOSED
        mock_cb.failure_count = 0
        mock_cb.name = "PartialAPI"
        
        validator.register_component("circuit_breaker", mock_cb)
        # Missing: fallback_response, json_escape
        
        status = validator.get_chain_status()
        assert status["valid"] == False
        assert "fallback_response" in status["missing"]
        assert "json_escape" in status["missing"]
    
    def test_health_score_with_partial_chain(self):
        """Health score reflects incomplete chain."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        
        # All healthy
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.CLOSED
        mock_cb.failure_count = 0
        mock_cb.name = "HealthyAPI"
        
        mock_fallback = Mock()
        mock_fallback.get_fallback = Mock(return_value={"status": "ok"})
        mock_fallback.strategy = "RETURN_NONE"
        
        validator.register_component("circuit_breaker", mock_cb)
        validator.register_component("fallback_response", mock_fallback)
        
        status = validator.get_chain_status()
        # 2/3 required components healthy = ~40-50 score
        assert status["health_score"] > 0
        assert status["health_score"] < 100
    
    def test_json_output_format(self):
        """Validator produces machine-readable JSON output."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.CLOSED
        mock_cb.failure_count = 0
        mock_cb.name = "TestAPI"
        
        validator.register_component("circuit_breaker", mock_cb)
        
        json_output = validator.to_json()
        parsed = json.loads(json_output)
        
        assert "valid" in parsed
        assert "components" in parsed
        assert "health_score" in parsed
        assert "timestamp" in parsed
    
    def test_quick_health_check(self):
        """Quick health check returns simple status."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.CLOSED
        mock_cb.failure_count = 0
        mock_cb.name = "QuickAPI"
        
        validator.register_component("circuit_breaker", mock_cb)
        
        health = validator.quick_check()
        assert health["status"] in ["healthy", "degraded", "critical"]
        assert "score" in health
    
    def test_component_validation_errors(self):
        """Invalid components are rejected."""
        from service_chain_validator import ServiceChainValidator
        
        validator = ServiceChainValidator()
        
        # None is not a valid component
        with pytest.raises(ValueError):
            validator.register_component("circuit_breaker", None)
    
    def test_unregister_component(self):
        """Components can be unregistered."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.CLOSED
        mock_cb.failure_count = 0
        mock_cb.name = "TempAPI"
        
        validator.register_component("circuit_breaker", mock_cb)
        assert "circuit_breaker" in validator.get_registered_components()
        
        validator.unregister_component("circuit_breaker")
        assert "circuit_breaker" not in validator.get_registered_components()
    
    def test_validation_report_includes_metadata(self):
        """Validation report includes versions and timestamps."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.CLOSED
        mock_cb.failure_count = 0
        mock_cb.name = "MetaAPI"
        
        validator.register_component("circuit_breaker", mock_cb)
        
        report = validator.get_validation_report()
        
        assert "generated_at" in report
        assert "version" in report
        assert "validator_version" in report


class TestCircuitBreakerState:
    """Test CircuitBreakerState enum."""
    
    def test_state_values(self):
        """State enum has expected values."""
        from service_chain_validator import CircuitBreakerState
        
        assert CircuitBreakerState.CLOSED.value == "CLOSED"
        assert CircuitBreakerState.OPEN.value == "OPEN"
        assert CircuitBreakerState.HALF_OPEN.value == "HALF_OPEN"


class TestValidationReport:
    """Test validation report generation."""
    
    def test_report_structure(self):
        """Report has expected structure."""
        from service_chain_validator import ServiceChainValidator, generate_validation_report
        
        report = generate_validation_report()
        
        assert "summary" in report
        assert "details" in report
        assert "recommendations" in report
    
    def test_report_with_mock_components(self):
        """Report includes mock component status."""
        from service_chain_validator import ServiceChainValidator
        from service_chain_validator import CircuitBreakerState
        
        validator = ServiceChainValidator()
        
        mock_cb = Mock()
        mock_cb.state = CircuitBreakerState.CLOSED
        mock_cb.failure_count = 0
        mock_cb.name = "ReportTestAPI"
        
        validator.register_component("circuit_breaker", mock_cb)
        
        report = validator.get_validation_report()
        
        assert report["summary"]["total_components"] >= 1
