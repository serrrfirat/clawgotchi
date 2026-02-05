"""Resilience Health Diagnostic Utility for Clawgotchi.

Checks health of all resilience utilities and reports status.
"""

import importlib
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path


class ResilienceDiagnostic:
    """
    Diagnostic tool for checking health of resilience utilities.
    
    Checks availability and status of:
    - circuit_breaker
    - timeout_budget
    - fallback_response
    - json_escape
    - moltbook_config
    - service_chain
    - permission_manifest_scanner
    - credential_rotation_alerts
    """
    
    # Components to check
    COMPONENTS = [
        "circuit_breaker",
        "timeout_budget",
        "fallback_response",
        "json_escape",
        "moltbook_config",
        "service_chain",
        "permission_manifest_scanner",
        "credential_rotation_alerts",
    ]
    
    # Module paths for each component (relative to project root)
    MODULE_PATHS = {
        "circuit_breaker": "skills.circuit_breaker.circuit_breaker",
        "timeout_budget": "skills.timeout_budget.timeout_budget",
        "fallback_response": "clawgotchi.resilience.fallback_response",
        "json_escape": "skills.json_escape.json_escape",
        "moltbook_config": "clawgotchi.resilience.moltbook_config",
        "permission_manifest_scanner": "skills.auto_updater.permission_manifest_scanner",
        "credential_rotation_alerts": "skills.auto_updater.credential_rotation_alerts",
        "service_chain": "clawgotchi.resilience.service_chain",
    }
    
    def __init__(self):
        """Initialize the diagnostic tool."""
        self._last_check: Optional[datetime] = None
        self._component_cache: Dict[str, Dict[str, Any]] = {}
        self._version_cache: Dict[str, Optional[str]] = {}
        self._refresh_cache()
    
    def _refresh_cache(self) -> None:
        """Refresh the component cache by checking all components."""
        self._last_check = datetime.utcnow()
        self._component_cache = {}
        
        for component in self.COMPONENTS:
            status = self._check_component(component)
            self._component_cache[component] = status
    
    def _get_module_version(self, module_name: str) -> Optional[str]:
        """Get version of a module if available."""
        if module_name in self._version_cache:
            return self._version_cache[module_name]
        
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", None)
            self._version_cache[module_name] = version
            return version
        except ImportError:
            self._version_cache[module_name] = None
            return None
    
    def _check_component(self, component: str) -> Dict[str, Any]:
        """
        Check the health of a single component.
        
        Args:
            component: Name of the component to check.
            
        Returns:
            Dict with status info.
        """
        module_path = self.MODULE_PATHS.get(component)
        
        if not module_path:
            return {
                "component": component,
                "status": "unknown",
                "message": "Component not configured",
                "available": False,
                "version": None,
                "error": "Unknown component",
            }
        
        try:
            module = importlib.import_module(module_path)
            # Try to get version
            version = getattr(module, "__version__", None)
            if version is None:
                # Try __package__ or other attributes
                version = getattr(module, "__version__", None)
            
            return {
                "component": component,
                "status": "healthy",
                "message": "Component is available and functional",
                "available": True,
                "version": version,
                "error": None,
            }
        except ImportError as e:
            return {
                "component": component,
                "status": "degraded",
                "message": f"Component import failed: {e}",
                "available": False,
                "version": None,
                "error": str(e),
            }
        except Exception as e:
            return {
                "component": component,
                "status": "degraded",
                "message": f"Component check failed: {e}",
                "available": False,
                "version": None,
                "error": str(e),
            }
    
    def quick_check(self) -> Dict[str, Any]:
        """
        Perform a quick health check.
        
        Returns:
            Dict with:
            - status: Overall status (healthy/degraded/critical)
            - healthy_count: Number of healthy components
            - total_count: Total number of components
        """
        self._refresh_cache()
        
        healthy = sum(1 for c in self._component_cache.values() if c["status"] == "healthy")
        degraded = sum(1 for c in self._component_cache.values() if c["status"] == "degraded")
        total = len(self.COMPONENTS)
        
        # Determine overall status
        if healthy == total:
            status = "healthy"
        elif healthy >= total * 0.5:
            status = "degraded"
        else:
            status = "critical"
        
        return {
            "status": status,
            "healthy_count": healthy,
            "degraded_count": degraded,
            "total_count": total,
            "timestamp": self._last_check.isoformat() if self._last_check else None,
        }
    
    def full_check(self) -> Dict[str, Any]:
        """
        Perform a full diagnostic check.
        
        Returns:
            Dict with:
            - components: Detailed status of each component
            - summary: Summary statistics
            - last_check_timestamp: ISO timestamp of last check
            - component_versions: Version info for components
        """
        self._refresh_cache()
        
        # Build components dict
        components = {}
        versions = {}
        
        for component, status in self._component_cache.items():
            components[component] = {
                "status": status["status"],
                "available": status["available"],
                "message": status.get("message", ""),
                "error": status.get("error"),
            }
            if status["version"]:
                versions[component] = status["version"]
        
        # Calculate summary
        healthy = sum(1 for c in self._component_cache.values() if c["status"] == "healthy")
        degraded = sum(1 for c in self._component_cache.values() if c["status"] == "degraded")
        unknown = sum(1 for c in self._component_cache.values() if c["status"] == "unknown")
        
        summary = {
            "overall_health_score": (healthy / len(self.COMPONENTS)) * 100 if self.COMPONENTS else 0,
            "components_checked": len(self.COMPONENTS),
            "healthy_count": healthy,
            "degraded_count": degraded,
            "unknown_count": unknown,
            "uptime_percent": (healthy / len(self.COMPONENTS)) * 100 if self.COMPONENTS else 0,
        }
        
        return {
            "components": components,
            "summary": summary,
            "last_check_timestamp": self._last_check.isoformat() if self._last_check else None,
            "component_versions": versions,
        }
    
    def get_component_status(self, component: str) -> Dict[str, Any]:
        """
        Get status of a specific component.
        
        Args:
            component: Name of the component.
            
        Returns:
            Dict with status info for the component.
        """
        if component not in self._component_cache:
            # Check if it's a valid component but not in cache
            if component in self.COMPONENTS:
                status = self._check_component(component)
                return status
            else:
                return {
                    "component": component,
                    "status": "unknown",
                    "message": "Component not in registry",
                    "available": False,
                    "version": None,
                    "error": "Unknown component",
                }
        
        return self._component_cache[component]
    
    def get_health_score(self) -> float:
        """
        Get overall health score as a percentage.
        
        Returns:
            Health score between 0 and 100.
        """
        self._refresh_cache()
        healthy = sum(1 for c in self._component_cache.values() if c["status"] == "healthy")
        return (healthy / len(self.COMPONENTS)) * 100 if self.COMPONENTS else 0
    
    def get_overall_status(self) -> str:
        """
        Get overall system status.
        
        Returns:
            Status string: healthy, degraded, critical, or unknown
        """
        self._refresh_cache()
        
        healthy = sum(1 for c in self._component_cache.values() if c["status"] == "healthy")
        degraded = sum(1 for c in self._component_cache.values() if c["status"] == "degraded")
        total = len(self.COMPONENTS)
        
        if total == 0:
            return "unknown"
        
        if healthy == total:
            return "healthy"
        elif healthy >= total * 0.5:
            return "degraded"
        else:
            return "critical"
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the diagnostic results.
        
        Returns:
            Dict with summary statistics.
        """
        self._refresh_cache()
        
        healthy = sum(1 for c in self._component_cache.values() if c["status"] == "healthy")
        degraded = sum(1 for c in self._component_cache.values() if c["status"] == "degraded")
        unknown = sum(1 for c in self._component_cache.values() if c["status"] == "unknown")
        
        return {
            "overall_health_score": (healthy / len(self.COMPONENTS)) * 100 if self.COMPONENTS else 0,
            "components_checked": len(self.COMPONENTS),
            "healthy_count": healthy,
            "degraded_count": degraded,
            "unknown_count": unknown,
            "last_check": self._last_check.isoformat() if self._last_check else None,
        }


def create_diagnostic() -> ResilienceDiagnostic:
    """Factory function to create a ResilienceDiagnostic instance."""
    return ResilienceDiagnostic()


def quick_health_check() -> Dict[str, Any]:
    """
    Convenience function for a quick health check.
    
    Returns:
        Quick health check results.
    """
    diagnostic = ResilienceDiagnostic()
    return diagnostic.quick_check()


if __name__ == "__main__":
    # Run a quick check if executed directly
    diagnostic = ResilienceDiagnostic()
    print("Quick Check:")
    print(diagnostic.quick_check())
    print("\nFull Check:")
    print(diagnostic.full_check())
