"""
ServiceDependencyChain - Orchestrates circuit breakers, timeouts, and fallbacks for agent services.

Provides a clean API for managing service dependencies with:
- Circuit breaker protection
- Timeout budgets per service
- Fallback responses on failure
- Health monitoring
- Chain execution with ordered dependencies

Usage:
    from service_chain import ServiceDependencyChain, ServiceConfig

    chain = ServiceDependencyChain()
    chain.add(ServiceConfig(name="moltbook_api", timeout_ms=3000, fallback_return={"error": "unavailable"}))
    chain.add(ServiceConfig(name="database", timeout_ms=5000))

    def fetch_data():
        return api.get("/data")

    result = chain.execute_service("moltbook_api", fetch_data)
    health = chain.get_health_status()
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import time
import threading


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Blocking calls
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


@dataclass
class ServiceConfig:
    """Configuration for a single service dependency."""
    name: str
    timeout_ms: int = 5000
    fallback_return: Optional[Any] = None
    circuit_failure_threshold: int = 5
    circuit_reset_timeout_sec: int = 30


@dataclass
class CircuitBreaker:
    """Simple circuit breaker implementation."""
    failure_threshold: int = 5
    reset_timeout_sec: int = 30
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record_failure(self):
        """Record a failure and potentially open circuit."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN

    def record_success(self):
        """Record a success and potentially close circuit."""
        with self.lock:
            self.failure_count = 0
            self.state = CircuitState.CLOSED

    def allow_request(self) -> bool:
        """Check if request should be allowed based on circuit state."""
        with self.lock:
            if self.state == CircuitState.CLOSED:
                return True
            if self.state == CircuitState.OPEN:
                # Check if reset timeout has passed
                if self.last_failure_time and (time.time() - self.last_failure_time) >= self.reset_timeout_sec:
                    self.state = CircuitState.HALF_OPEN
                    return True
                return False
            # HALF_OPEN - allow single request
            return True


@dataclass
class DependencyNode:
    """Represents a single service in the dependency chain."""
    name: str
    config: ServiceConfig
    circuit_breaker: CircuitBreaker = field(init=False)

    def __post_init__(self):
        """Initialize circuit breaker from config."""
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.circuit_failure_threshold,
            reset_timeout_sec=self.config.circuit_reset_timeout_sec
        )

    def execute(self, func: Callable[[], Any]) -> Any:
        """Execute a function with circuit breaker, timeout, and fallback protection."""
        # Check circuit breaker
        if not self.circuit_breaker.allow_request():
            if self.config.fallback_return is not None:
                return self.config.fallback_return
            raise CircuitOpenError(f"Circuit open for {self.name}")

        # Check timeout and execute
        timeout_sec = self.config.timeout_ms / 1000.0
        start_time = time.time()

        try:
            result = func()
            elapsed = time.time() - start_time

            if elapsed > timeout_sec:
                # Timeout - treat as failure
                self.circuit_breaker.record_failure()
                if self.config.fallback_return is not None:
                    return self.config.fallback_return
                raise TimeoutError(f"Timeout executing {self.name} after {timeout_sec}s")

            # Success - reset circuit
            self.circuit_breaker.record_success()
            return result

        except Exception as e:
            # Failure - record in circuit breaker
            self.circuit_breaker.record_failure()
            if self.config.fallback_return is not None:
                return self.config.fallback_return
            raise

    def get_state(self) -> Dict[str, Any]:
        """Get current state of this node."""
        return {
            "name": self.name,
            "state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "timeout_ms": self.config.timeout_ms,
            "has_fallback": self.config.fallback_return is not None
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and no fallback is configured."""
    pass


class ServiceDependencyChain:
    """
    Orchestrates multiple service dependencies with circuit breakers, timeouts, and fallbacks.

    Example:
        chain = ServiceDependencyChain()
        chain.add(ServiceConfig(name="moltbook", timeout_ms=3000, fallback_return={"error": True}))
        chain.add(ServiceConfig(name="cache", timeout_ms=1000))

        results = chain.execute_chain([
            ("moltbook", lambda: api.get("/posts")),
            ("cache", lambda: cache.get("data"))
        ])
    """

    def __init__(self):
        self._dependencies: Dict[str, DependencyNode] = {}
        self._execution_order: List[str] = []

    def add(self, config: ServiceConfig) -> "ServiceDependencyChain":
        """Add a service dependency to the chain. Returns self for chaining."""
        self._dependencies[config.name] = DependencyNode(config.name, config)
        if config.name not in self._execution_order:
            self._execution_order.append(config.name)
        return self

    def set_order(self, order: List[str]) -> "ServiceDependencyChain":
        """Set explicit execution order. All named services must exist."""
        self._execution_order = order
        return self

    def get(self, name: str) -> Optional[DependencyNode]:
        """Get a dependency node by name."""
        return self._dependencies.get(name)

    def execute_service(self, name: str, func: Callable[[], Any]) -> Any:
        """Execute a single service with full protection."""
        node = self._dependencies.get(name)
        if node is None:
            raise ValueError(f"Unknown service: {name}")
        return node.execute(func)

    def execute_chain(
        self,
        funcs: Optional[List[Tuple[str, Callable[[], Any]]]] = None
    ) -> Dict[str, Any]:
        """
        Execute all services in order.

        Args:
            funcs: Optional list of (name, function) pairs. If None, executes with no functions.

        Returns:
            Dict mapping service name to result (or fallback/error info)
        """
        results = {}
        execution_list = funcs or [(name, lambda n=name: None) for name in self._execution_order]

        for name, func in execution_list:
            if name not in self._dependencies:
                results[name] = {"status": "unknown", "error": f"Service {name} not configured"}
                continue

            try:
                node = self._dependencies[name]
                result = node.execute(func)
                results[name] = {"status": "success", "result": result}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}

        return results

    def get_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all dependencies."""
        return {
            name: node.get_state()
            for name, node in self._dependencies.items()
        }

    def reset(self) -> "ServiceDependencyChain":
        """Reset all circuit breakers to closed state."""
        for node in self._dependencies.values():
            node.circuit_breaker.state = CircuitState.CLOSED
            node.circuit_breaker.failure_count = 0
        return self

    def __len__(self) -> int:
        """Return number of dependencies."""
        return len(self._dependencies)

    def __contains__(self, name: str) -> bool:
        """Check if service exists in chain."""
        return name in self._dependencies

    def __repr__(self) -> str:
        services = list(self._dependencies.keys())
        return f"ServiceDependencyChain({services})"


def create_moltbook_chain(
    api_key: str,
    fallback_return: Optional[Any] = None
) -> ServiceDependencyChain:
    """
    Create a pre-configured chain for Moltbook API access.

    Args:
        api_key: Moltbook API key
        fallback_return: Value to return if Moltbook is unavailable

    Returns:
        Configured ServiceDependencyChain ready for Moltbook operations
    """
    chain = ServiceDependencyChain()
    chain.add(ServiceConfig(
        name="moltbook_api",
        timeout_ms=5000,
        fallback_return=fallback_return or {"error": "moltbook_unavailable"},
        circuit_failure_threshold=3,
        circuit_reset_timeout_sec=60
    ))
    return chain


# Convenience function for quick chain creation
def quick_chain(
    *service_names: str,
    timeout_ms: int = 5000,
    fallback: Any = None
) -> ServiceDependencyChain:
    """
    Create a chain with multiple services quickly.

    Example:
        chain = quick_chain("api", "cache", "database", timeout_ms=3000, fallback={"status": "degraded"})
    """
    chain = ServiceDependencyChain()
    for name in service_names:
        chain.add(ServiceConfig(
            name=name,
            timeout_ms=timeout_ms,
            fallback_return=fallback
        ))
    return chain
