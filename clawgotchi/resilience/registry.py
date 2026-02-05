"""Registry for Clawgotchi's resilience utilities."""

from datetime import datetime
from typing import Any, Optional
import importlib
import inspect


class ResilienceRegistry:
    """Central registry for resilience utilities."""
    
    COMPONENTS = {
        "circuit_breaker": {
            "module": "skills.circuit_breaker.circuit_breaker",
            "description": "Circuit breaker pattern for service protection",
        },
        "timeout_budget": {
            "module": "skills.timeout_budget.timeout_budget",
            "description": "Timeout budget management for operations",
        },
        "fallback_response": {
            "module": "clawgotchi.resilience.fallback_response",
            "description": "Fallback strategies for unavailable services",
        },
        "json_escape": {
            "module": "skills.json_escape.json_escape",
            "description": "JSON escaping for Moltbook posts",
        },
        "moltbook_config": {
            "module": "clawgotchi.resilience.moltbook_config",
            "description": "Moltbook API configuration helper",
        },
        "permission_manifest_scanner": {
            "module": "skills.auto_updater.permission_manifest_scanner",
            "description": "Security spec for skill permissions",
        },
        "credential_rotation_alerts": {
            "module": "skills.auto_updater.credential_rotation_alerts",
            "description": "Alert on credential rotation needs",
        },
    }
    
    def __init__(self):
        self._components: dict[str, dict[str, Any]] = {}
        self._last_refresh: Optional[datetime] = None
        self._refresh()
    
    def _refresh(self) -> None:
        """Scan all registered components and update registry."""
        self._components = {}
        for name, config in self.COMPONENTS.items():
            self._components[name] = {
                "name": name,
                "module": config["module"],
                "description": config["description"],
                "available": False,
                "functions": [],
                "last_check": datetime.utcnow().isoformat(),
                "error": None,
            }
            
            try:
                module = importlib.import_module(config["module"])
                functions = [
                    name for name, obj in inspect.getmembers(module, inspect.isfunction)
                    if not name.startswith("_")
                ]
                self._components[name]["available"] = True
                self._components[name]["functions"] = functions
            except ImportError as e:
                self._components[name]["error"] = str(e)
        
        self._last_refresh = datetime.utcnow()
    
    def list_components(self, show_unavailable: bool = False) -> list[dict[str, Any]]:
        """List all registered components.
        
        Args:
            show_unavailable: Include components that failed to import.
            
        Returns:
            List of component info dictionaries.
        """
        if show_unavailable:
            return list(self._components.values())
        return [c for c in self._components.values() if c["available"]]
    
    def get_component(self, name: str) -> Optional[dict[str, Any]]:
        """Get info about a specific component.
        
        Args:
            name: Component name (e.g., 'circuit_breaker').
            
        Returns:
            Component info dict or None if not found.
        """
        return self._components.get(name)
    
    def get_healthy_count(self) -> int:
        """Count components that are available."""
        return sum(1 for c in self._components.values() if c["available"])
    
    def get_unhealthy_count(self) -> int:
        """Count components that failed to import."""
        return sum(1 for c in self._components.values() if not c["available"])
    
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the registry state."""
        return {
            "total_components": len(self._components),
            "healthy": self.get_healthy_count(),
            "unhealthy": self.get_unhealthy_count(),
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "uptime_percent": (
                self.get_healthy_count() / len(self._components) * 100
                if self._components else 0
            ),
        }
    
    def reload(self) -> None:
        """Re-scan all components."""
        self._refresh()


# Global registry instance
_registry: Optional[ResilienceRegistry] = None


def get_registry() -> ResilienceRegistry:
    """Get or create the global registry instance."""
    global _registry
    if _registry is None:
        _registry = ResilienceRegistry()
    return _registry


def list_all(show_unavailable: bool = False) -> list[dict[str, Any]]:
    """Convenience function to list all components."""
    return get_registry().list_components(show_unavailable)


def get_summary() -> dict[str, Any]:
    """Convenience function to get registry summary."""
    return get_registry().get_summary()
