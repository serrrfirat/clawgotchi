"""
Timeout Budget Utility for Agent Operations

Enforces maximum execution time for agent operations, preventing hangs.
Designed to pair with Circuit Breaker for comprehensive dependency protection:

- Circuit Breaker: Stop hammering dead services
- Timeout Budget: Don't hang on slow operations

Usage:
    from timeout_budget import TimeoutBudget, with_timeout, BudgetCategory

    # Basic timeout enforcement
    tb = TimeoutBudget(max_duration_ms=5000)  # 5 second budget
    
    with tb:
        result = slow_operation()  # Will timeout if >5s
        process(result)

    # Decorator usage
    @with_timeout(timeout_ms=3000, on_timeout="return_none")
    def fetch_data():
        return external_api_call()

    # Category-based budgets (e.g., per API provider)
    monitor = get_global_monitor()
    category = BudgetCategory("openai", total_ms=60000)  # $0.06/min budget
    monitor.register_category(category)
    
    budget = monitor.allocate("openai", 1000)  # 1s for this call
    with budget:
        response = openai.ChatCompletion.create(...)
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional


class TimeoutExceededError(Exception):
    """Raised when a timeout budget is exceeded."""
    
    def __init__(self, operation_name: str = "Operation", duration_ms: int = 0):
        self.operation_name = operation_name
        self.duration_ms = duration_ms
        message = f"{operation_name} exceeded timeout budget ({duration_ms}ms)"
        super().__init__(message)


class BudgetExceededError(Exception):
    """Raised when a budget category is exhausted."""
    
    def __init__(self, category_name: str = "Category", remaining_ms: int = 0):
        self.category_name = category_name
        self.remaining_ms = remaining_ms
        message = f"Budget exceeded for {category_name} ({remaining_ms}ms remaining)"
        super().__init__(message)


class TimeoutStrategy(Enum):
    """What to do when timeout occurs."""
    RAISE_ERROR = "raise"
    RETURN_NONE = "return_none"
    RETURN_VALUE = "return_value"


@dataclass
class TimeoutBudget:
    """
    A budget for timeout enforcement on an operation.
    
    Tracks elapsed time and prevents operations from exceeding their budget.
    
    Args:
        max_duration_ms: Maximum duration in milliseconds
        name: Optional name for debugging
    
    Usage:
        tb = TimeoutBudget(max_duration_ms=5000)  # 5 second budget
        
        with tb:
            result = slow_operation()
        
        # Or use the decorator
        @with_timeout(timeout_ms=5000)
        def my_func():
            ...
    """
    max_duration_ms: int
    name: str = "TimeoutBudget"
    _start_time: float = field(default=None, init=False, repr=False)
    _exhausted: bool = field(default=False, init=False, repr=False)
    
    def __post_init__(self):
        if self.max_duration_ms < 0:
            raise ValueError("max_duration_ms must be non-negative")
        self._start_time = time.time()
        self._exhausted = self.max_duration_ms == 0
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self._start_time is None:
            return 0
        elapsed = (time.time() - self._start_time) * 1000
        if self._exhausted:
            return self.max_duration_ms
        return elapsed
    
    @property
    def remaining_ms(self) -> int:
        """Get remaining time in milliseconds."""
        remaining = self.max_duration_ms - int(self.elapsed_ms)
        return max(0, remaining)
    
    @property
    def is_exhausted(self) -> bool:
        """Check if the budget is exhausted."""
        if self._exhausted:
            return True
        if self.remaining_ms <= 0:
            self._exhausted = True
            return True
        return False
    
    def check(self) -> None:
        """
        Check if budget is exhausted.
        
        Raises:
            TimeoutExceededError: If budget is exhausted
        """
        if self.is_exhausted:
            raise TimeoutExceededError(self.name, self.max_duration_ms)
    
    def __enter__(self):
        """Context manager entry - starts tracking time."""
        self._start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - checks if budget was exceeded."""
        if exc_type is None:  # No exception occurred
            self.check()
        return False


def _parse_on_timeout(value: str) -> TimeoutStrategy:
    """Parse on_timeout string to enum."""
    if value == "return_none":
        return TimeoutStrategy.RETURN_NONE
    elif value == "return_value":
        return TimeoutStrategy.RETURN_VALUE
    return TimeoutStrategy.RAISE_ERROR


def with_timeout(
    timeout_ms: int,
    on_timeout: str = "raise",
    timeout_value: Any = None,
    operation_name: str = "Function"
) -> Callable:
    """
    Decorator to enforce timeout on a function.
    
    Args:
        timeout_ms: Maximum execution time in milliseconds
        on_timeout: "raise", "return_none", or "return_value"
        timeout_value: Value to return if on_timeout="return_value"
        operation_name: Name for error messages
    
    Returns:
        Decorated function with timeout enforcement
    
    Usage:
        @with_timeout(timeout_ms=5000)
        def api_call():
            return requests.get(url)
        
        @with_timeout(timeout_ms=1000, on_timeout="return_none")
        def quick_check():
            return cache.get(key)
    """
    strategy = _parse_on_timeout(on_timeout)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            tb = TimeoutBudget(max_duration_ms=timeout_ms, name=operation_name)
            
            result = None
            exception = None
            
            def target():
                nonlocal result, exception
                try:
                    with tb:
                        result = func(*args, **kwargs)
                except Exception as e:
                    exception = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout_ms / 1000.0)
            
            if thread.is_alive():
                # Timeout occurred
                if strategy == TimeoutStrategy.RAISE_ERROR:
                    raise TimeoutExceededError(operation_name, timeout_ms)
                elif strategy == TimeoutStrategy.RETURN_NONE:
                    return None
                elif strategy == TimeoutStrategy.RETURN_VALUE:
                    return timeout_value
            
            if exception is not None:
                raise exception
            
            return result
        return wrapper
    return decorator


@dataclass
class BudgetCategory:
    """
    A category for tracking budget allocations.
    
    Useful for tracking budgets across multiple operations of the same type.
    
    Args:
        name: Category name (e.g., "openai_api", "browser_session")
        total_budget_ms: Total budget in milliseconds for this category
    
    Usage:
        category = BudgetCategory("openai", total_ms=60000)  # $0.06/min
        
        # Allocate for individual operations
        budget = category.allocate(1000)  # 1s for this call
        with budget:
            response = openai_call()
    """
    name: str
    total_budget_ms: int
    allocated_ms: int = field(default=0, init=False)
    _allocations: Dict[str, 'TimeoutBudget'] = field(default_factory=dict, init=False)
    
    def __post_init__(self):
        if self.total_budget_ms < 0:
            raise ValueError("total_budget_ms must be non-negative")
        self.allocated_ms = 0
        self._allocations = {}
    
    def allocate(
        self,
        duration_ms: int,
        allocation_id: Optional[str] = None
    ) -> TimeoutBudget:
        """
        Allocate a budget for an operation.
        
        Args:
            duration_ms: Maximum duration for this allocation
            allocation_id: Optional unique ID for this allocation
        
        Returns:
            TimeoutBudget for the allocation
        
        Raises:
            BudgetExceededError: If category budget is exceeded
        """
        if self.remaining_ms < duration_ms:
            raise BudgetExceededError(self.name, self.remaining_ms)
        
        allocation_id = allocation_id or f"alloc_{len(self._allocations)}"
        budget = TimeoutBudget(
            max_duration_ms=duration_ms,
            name=f"{self.name}_{allocation_id}"
        )
        
        self._allocations[allocation_id] = budget
        self.allocated_ms += duration_ms
        return budget
    
    def release(self, allocation_id: str) -> None:
        """Release an allocation back to the category pool."""
        if allocation_id in self._allocations:
            budget = self._allocations[allocation_id]
            self.allocated_ms -= budget.max_duration_ms
            del self._allocations[allocation_id]
    
    @property
    def remaining_ms(self) -> int:
        """Get remaining budget in the category."""
        return max(0, self.total_budget_ms - self.allocated_ms)
    
    @property
    def usage_percent(self) -> float:
        """Get usage as a percentage."""
        if self.total_budget_ms == 0:
            return 100.0
        return (self.allocated_ms / self.total_budget_ms) * 100


class BudgetMonitor:
    """
    Global monitor for tracking budget categories.
    
    Singleton pattern for easy access across the agent.
    
    Usage:
        monitor = get_global_monitor()
        
        # Register categories
        monitor.register_category(BudgetCategory("openai", total_ms=60000))
        monitor.register_category(BudgetCategory("anthropic", total_ms=60000))
        
        # Allocate from categories
        budget = monitor.allocate("openai", 1000)  # 1 second
        with budget:
            result = openai_call()
    """
    _instance: Optional['BudgetMonitor'] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._categories: Dict[str, BudgetCategory] = {}
        self._initialized = True
    
    def register_category(self, category: BudgetCategory) -> None:
        """Register a budget category."""
        self._categories[category.name] = category
    
    def get_category(self, name: str) -> Optional[BudgetCategory]:
        """Get a budget category by name."""
        return self._categories.get(name)
    
    def allocate(
        self,
        category_name: str,
        duration_ms: int,
        allocation_id: Optional[str] = None
    ) -> TimeoutBudget:
        """
        Allocate from a category.
        
        Args:
            category_name: Name of the category
            duration_ms: Duration to allocate
            allocation_id: Optional allocation ID
        
        Returns:
            TimeoutBudget for the allocation
        
        Raises:
            ValueError: If category doesn't exist
            BudgetExceededError: If category budget is exceeded
        """
        category = self._categories.get(category_name)
        if category is None:
            raise ValueError(f"Category '{category_name}' not registered")
        return category.allocate(duration_ms, allocation_id)
    
    def release(self, category_name: str, allocation_id: str) -> None:
        """Release an allocation from a category."""
        category = self._categories.get(category_name)
        if category is not None:
            category.release(allocation_id)
    
    def get_all_categories(self) -> Dict[str, BudgetCategory]:
        """Get all registered categories."""
        return self._categories.copy()
    
    def get_status(self, category_name: str) -> Optional[Dict[str, Any]]:
        """Get status summary for a category."""
        category = self._categories.get(category_name)
        if category is None:
            return None
        return {
            "name": category.name,
            "total_ms": category.total_budget_ms,
            "allocated_ms": category.allocated_ms,
            "remaining_ms": category.remaining_ms,
            "usage_percent": category.usage_percent
        }
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all categories."""
        return {
            name: self.get_status(name)
            for name in self._categories
        }


# Global monitor singleton
_monitor: Optional[BudgetMonitor] = None


def get_global_monitor() -> BudgetMonitor:
    """Get the global budget monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = BudgetMonitor()
    return _monitor


# CLI interface
if __name__ == "__main__":
    print("Timeout Budget Utility Demo")
    print("=" * 50)
    
    # Basic budget demo
    print("\n1. Basic Timeout Budget")
    print("-" * 30)
    tb = TimeoutBudget(max_duration_ms=1000)
    print(f"Budget: {tb.max_duration_ms}ms")
    
    with tb:
        print(f"  Working... elapsed: {tb.elapsed_ms:.1f}ms")
        time.sleep(0.1)
        print(f"  Still going... elapsed: {tb.elapsed_ms:.1f}ms")
    
    print(f"  Completed! Used: {tb.elapsed_ms:.1f}ms")
    
    # Timeout demo
    print("\n2. Timeout Enforcement")
    print("-" * 30)
    
    @with_timeout(timeout_ms=100, on_timeout="return_none")
    def will_timeout():
        time.sleep(0.3)
        return "done"
    
    result = will_timeout()
    print(f"  Result: {result}")
    print("  (Expected: None - function timed out)")
    
    # Budget category demo
    print("\n3. Budget Categories")
    print("-" * 30)
    
    category = BudgetCategory("api_calls", total_ms=5000)
    print(f"  Category: {category.name}")
    print(f"  Total budget: {category.total_budget_ms}ms")
    
    budget1 = category.allocate(1000)
    print(f"  Allocated 1000ms, remaining: {category.remaining_ms}ms")
    
    budget2 = category.allocate(2000)
    print(f"  Allocated 2000ms, remaining: {category.remaining_ms}ms")
    
    print(f"  Usage: {category.usage_percent:.1f}%")
    
    # Global monitor demo
    print("\n4. Global Budget Monitor")
    print("-" * 30)
    
    monitor = get_global_monitor()
    monitor.register_category(BudgetCategory("global_test", total_ms=10000))
    
    budget = monitor.allocate("global_test", 500)
    print(f"  Global allocation: 500ms from global_test category")
    print(f"  Category status: {monitor.get_status('global_test')}")
    
    print("\n" + "=" * 50)
    print("Demo complete!")
