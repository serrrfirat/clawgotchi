"""Clawgotchi resilience utilities package."""

from .registry import (
    ResilienceRegistry,
    get_registry,
    list_all,
    get_summary,
)

from .degradation_coordinator import (
    GracefulDegradationCoordinator,
    DegradationLevel,
    DegradationConfig,
    DegradationState,
    DegradationContext,
    DegradationOperation,
    create_degradation_coordinator,
)

__all__ = [
    "ResilienceRegistry",
    "get_registry",
    "list_all", 
    "get_summary",
    "GracefulDegradationCoordinator",
    "DegradationLevel",
    "DegradationConfig",
    "DegradationState",
    "DegradationContext",
    "DegradationOperation",
    "create_degradation_coordinator",
]
