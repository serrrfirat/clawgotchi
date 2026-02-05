"""Timeout Budget pattern for Clawgotchi.

Tracks remaining time for operations and enforces timeout budgets.
Used with circuit breaker for graceful degradation.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import threading


class BudgetCategory(Enum):
    """Categories of operations with different budget allocations."""
    MOLTBOOK_API = "moltbook_api"
    GITHUB_API = "github_api"
    OPENCLAW_API = "openclaw_api"
    FILE_IO = "file_io"
    AGENT_REASONING = "agent_reasoning"
    UNKNOWN = "unknown"


@dataclass
class TimeoutBudget:
    """A budget for how long an operation can take."""
    default_budget_ms: int = 5000
    category: BudgetCategory = BudgetCategory.UNKNOWN
    _remaining_ms: int = field(default=5000, init=False)
    _start_time: datetime = field(default_factory=datetime.now, init=False)
    
    def reset(self):
        """Reset the budget timer."""
        self._remaining_ms = self.default_budget_ms
        self._start_time = datetime.now()
    
    def remaining_ms(self) -> int:
        """Get remaining time in milliseconds."""
        elapsed = datetime.now() - self._start_time
        return max(0, self.default_budget_ms - int(elapsed.total_seconds() * 1000))
    
    def is_expired(self) -> bool:
        """Check if budget has been exhausted."""
        return self.remaining_ms() <= 0
    
    def check(self) -> bool:
        """Check if operation should continue. Returns False if expired."""
        return not self.is_expired()
    
    def get_state(self) -> dict:
        """Get current state for monitoring."""
        return {
            "category": self.category.value,
            "remaining_ms": self.remaining_ms(),
            "is_expired": self.is_expired()
        }


class BudgetManager:
    """
    Manages timeout budgets for different operation categories.
    """
    
    def __init__(self, default_budget_ms: int = 5000):
        self.default_budget_ms = default_budget_ms
        self._budgets: Dict[str, TimeoutBudget] = {}
        self._lock = threading.Lock()
    
    def create_budget(
        self,
        category: BudgetCategory,
        budget_ms: Optional[int] = None
    ) -> TimeoutBudget:
        """Create a new budget for a category."""
        actual_ms = budget_ms or self.default_budget_ms
        budget = TimeoutBudget(
            default_budget_ms=actual_ms,
            category=category,
        )
        with self._lock:
            self._budgets[category.value] = budget
        return budget
    
    def get_budget(self, category: BudgetCategory) -> Optional[TimeoutBudget]:
        """Get existing budget for a category."""
        with self._lock:
            return self._budgets.get(category.value)
    
    def check_category(self, category: BudgetCategory) -> bool:
        """Check if a category budget is still valid."""
        budget = self.get_budget(category)
        if budget is None:
            return True  # No budget means unlimited
        return budget.check()
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state of all budgets for monitoring."""
        with self._lock:
            return {
                cat: budget.get_state() 
                for cat, budget in self._budgets.items()
            }
    
    def reset(self):
        """Reset all budgets."""
        with self._lock:
            self._budgets.clear()


def create_budget_manager(default_budget_ms: int = 5000) -> BudgetManager:
    """Factory function to create a budget manager."""
    return BudgetManager(default_budget_ms=default_budget_ms)
