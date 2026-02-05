"""
Service Chain Validator for Resilience Utilities
"""

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ComponentType(Enum):
    CIRCUIT_BREAKER = "circuit_breaker"
    FALLBACK_RESPONSE = "fallback_response"
    JSON_ESCAPE = "json_escape"
    TIMEOUT_BUDGET = "timeout_budget"
    MOLTBOOK_CONFIG = "moltbook_config"
    PERMISSION_SCANNER = "permission_manifest_scanner"
    CREDENTIAL_ROTATION = "credential_rotation_alerts"
    MEMORY_TRIAGE = "memory_triage"
    SESSION_HEALTH = "session_health"


@dataclass
class ComponentInfo:
    name: str
    type: str
    healthy: bool
    details: dict = field(default_factory=dict)


@dataclass
class ValidationStatus:
    valid: bool
    components: list
    health_score: int
    missing: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))


class ServiceChainValidator:
    """
    Validates that resilience components are correctly wired together.
    """
    
    REQUIRED_COMPONENTS = {
        ComponentType.CIRCUIT_BREAKER,
        ComponentType.FALLBACK_RESPONSE,
        ComponentType.JSON_ESCAPE,
    }
    
    OPTIONAL_COMPONENTS = {
        ComponentType.TIMEOUT_BUDGET,
        ComponentType.MOLTBOOK_CONFIG,
        ComponentType.PERMISSION_SCANNER,
        ComponentType.CREDENTIAL_ROTATION,
        ComponentType.MEMORY_TRIAGE,
        ComponentType.SESSION_HEALTH,
    }
    
    def __init__(self):
        self._components: dict = {}
        self._component_info: dict[str, dict[str, Any]] = {}
    
    def register_component(self, name: str, component: Any) -> None:
        if name is None or name == "":
            raise ValueError("Component name cannot be empty")
        if component is None:
            raise ValueError(f"Component '{name}' cannot be None")
        
        component_type = self._get_component_type(name)
        healthy = self._check_component_health(name, component)
        details = self._extract_component_details(name, component)
        
        self._components[name] = component
        self._component_info[name] = {
            "name": details.get("name", name),
            "type": component_type.value if component_type else "unknown",
            "healthy": healthy,
            "details": details
        }
    
    def unregister_component(self, name: str) -> bool:
        if name in self._components:
            del self._components[name]
            del self._component_info[name]
            return True
        return False
    
    def get_registered_components(self) -> dict[str, dict]:
        return self._component_info.copy()
    
    def get_component(self, name: str) -> Optional[Any]:
        return self._components.get(name)
    
    def _get_component_type(self, name: str) -> Optional[ComponentType]:
        name_lower = name.lower()
        for comp_type in ComponentType:
            if comp_type.value == name_lower:
                return comp_type
        return None
    
    def _check_component_health(self, name: str, component: Any) -> bool:
        try:
            if hasattr(component, 'state'):
                if hasattr(component.state, 'value'):
                    return component.state.value != "OPEN"
                return True
            
            if hasattr(component, 'strategy'):
                return component.strategy is not None
            
            if hasattr(component, 'escape_for_moltbook'):
                return callable(component.escape_for_moltbook)
            
            return True
        except Exception:
            return False
    
    def _extract_component_details(self, name: str, component: Any) -> dict:
        details = {}
        
        try:
            if hasattr(component, 'state'):
                if hasattr(component.state, 'value'):
                    details['state'] = component.state.value
                else:
                    details['state'] = str(component.state)
            
            if hasattr(component, 'failure_count'):
                details['failure_count'] = component.failure_count
            
            if hasattr(component, 'name'):
                details['name'] = component.name
            
            if hasattr(component, 'strategy'):
                details['strategy'] = str(component.strategy)
            
            if hasattr(component, '__class__'):
                details['class'] = component.__class__.__name__
                
        except Exception:
            pass
        
        return details
    
    def get_chain_status(self) -> dict:
        if len(self._components) == 0:
            return {
                "valid": True,
                "components": [],
                "health_score": 100,
                "missing": [],
                "errors": [],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }
        
        registered_types = {self._get_component_type(name) for name in self._components}
        registered_types = {t for t in registered_types if t is not None}
        
        missing = []
        for required in self.REQUIRED_COMPONENTS:
            if required not in registered_types:
                missing.append(required.value)
        
        errors = []
        for name, info in self._component_info.items():
            if info["type"] == "circuit_breaker" and not info["healthy"]:
                errors.append(f"{name} is OPEN")
        
        # Calculate health score
        healthy_required = sum(1 for info in self._component_info.values() 
                              if info["type"] in [ct.value for ct in self.REQUIRED_COMPONENTS] and info["healthy"])
        healthy_optional = sum(1 for info in self._component_info.values() 
                              if info["type"] not in [ct.value for ct in self.REQUIRED_COMPONENTS] and info["healthy"])
        
        required_count = len(self.REQUIRED_COMPONENTS)
        optional_count = len(self.OPTIONAL_COMPONENTS)
        
        # Base score from required components
        required_score = (healthy_required / required_count) * 100 if required_count > 0 else 0
        
        # Bonus from optional components (max 20 bonus points)
        optional_bonus = (healthy_optional / optional_count) * 20 if optional_count > 0 else 0
        
        health_score = int(required_score + optional_bonus)
        
        valid = len(missing) == 0 and len(errors) == 0
        
        return {
            "valid": valid,
            "components": list(self._component_info.values()),
            "health_score": health_score,
            "missing": missing,
            "errors": errors,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    
    def quick_check(self) -> dict:
        status = self.get_chain_status()
        
        if status["health_score"] >= 90:
            overall = "healthy"
        elif status["health_score"] >= 60:
            overall = "degraded"
        else:
            overall = "critical"
        
        return {
            "status": overall,
            "score": status["health_score"],
            "valid": status["valid"],
            "components": len(status["components"]),
            "missing": len(status["missing"])
        }
    
    def to_json(self) -> str:
        return json.dumps(self.get_chain_status(), indent=2)
    
    def get_validation_report(self) -> dict:
        status = self.get_chain_status()
        
        summary = {
            "valid": status["valid"],
            "health_score": status["health_score"],
            "total_components": len(status["components"]),
            "healthy_components": sum(1 for c in status["components"] if c["healthy"]),
            "missing_required": len(status["missing"]),
            "errors": len(status["errors"])
        }
        
        details = {
            "registered_components": status["components"],
            "missing_dependencies": status["missing"],
            "validation_errors": status["errors"]
        }
        
        recommendations = []
        
        if status["missing"]:
            missing_str = ", ".join(status["missing"])
            recommendations.append(f"Register missing components: {missing_str}")
        
        for error in status["errors"]:
            recommendations.append(f"Fix error: {error}")
        
        if status["health_score"] < 100:
            recommendations.append("Review component configurations for optimization")
        
        return {
            "summary": summary,
            "details": details,
            "recommendations": recommendations,
            "generated_at": status["timestamp"],
            "version": "1.0.0",
            "validator_version": "1.0.0"
        }


def generate_validation_report() -> dict:
    validator = ServiceChainValidator()
    return validator.get_validation_report()


if __name__ == "__main__":
    from unittest.mock import Mock
    
    print("Service Chain Validator")
    print("=" * 50)
    
    validator = ServiceChainValidator()
    
    mock_cb = Mock()
    mock_cb.state = CircuitBreakerState.CLOSED
    mock_cb.failure_count = 0
    mock_cb.name = "TestAPI"
    
    mock_fallback = Mock()
    mock_fallback.get_fallback = Mock(return_value={"status": "cached"})
    mock_fallback.strategy = "RETURN_CACHED"
    
    mock_escape = Mock()
    mock_escape.escape_for_moltbook = Mock(return_value="safe")
    
    validator.register_component("circuit_breaker", mock_cb)
    validator.register_component("fallback_response", mock_fallback)
    validator.register_component("json_escape", mock_escape)
    
    print("\nRegistered Components:")
    for name, info in validator.get_registered_components().items():
        print(f"  - {name}: {info['type']} ({'healthy' if info['healthy'] else 'unhealthy'})")
    
    print("\nQuick Health Check:")
    health = validator.quick_check()
    print(f"  Status: {health['status']}")
    print(f"  Score: {health['score']}")
    
    print("\nFull Validation Report:")
    report = validator.get_validation_report()
    print(json.dumps(report, indent=2))
    
    print("\n" + "=" * 50)
    print("Validation complete!")
