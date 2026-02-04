"""
Test suite for Timeout Budget Utility
"""

import time
import pytest
from timeout_budget import (
    TimeoutBudget,
    TimeoutExceededError,
    BudgetExceededError,
    with_timeout,
    get_global_monitor,
    BudgetCategory,
)


class TestTimeoutBudget:
    """Tests for the TimeoutBudget class."""
    
    def test_timeout_budget_initialization(self):
        """Test that timeout budget initializes correctly."""
        tb = TimeoutBudget(max_duration_ms=5000)
        assert tb.max_duration_ms == 5000
        assert tb.remaining_ms == 5000
        assert not tb.is_exhausted
    
    def test_elapsed_time_tracking(self):
        """Test that elapsed time is tracked correctly."""
        tb = TimeoutBudget(max_duration_ms=100)
        time.sleep(0.05)
        elapsed = tb.elapsed_ms
        assert elapsed >= 40
        assert elapsed < 100
    
    def test_budget_exhaustion(self):
        """Test that budget tracks exhaustion correctly."""
        tb = TimeoutBudget(max_duration_ms=10)
        time.sleep(0.05)
        assert tb.is_exhausted
        assert tb.remaining_ms == 0
    
    def test_remaining_calculation(self):
        """Test that remaining time is calculated correctly."""
        tb = TimeoutBudget(max_duration_ms=1000)
        time.sleep(0.1)
        remaining = tb.remaining_ms
        assert remaining >= 800
        assert remaining <= 1000


class TestTimeoutBudgetContextManager:
    """Tests for timeout budget context manager usage."""
    
    def test_context_manager_basic(self):
        """Test basic context manager functionality."""
        with TimeoutBudget(max_duration_ms=1000) as tb:
            assert tb.remaining_ms <= 1000
    
    def test_context_manager_elapsed_access(self):
        """Test that elapsed time is accessible in context."""
        with TimeoutBudget(max_duration_ms=1000) as tb:
            time.sleep(0.05)
            elapsed = tb.elapsed_ms
            assert elapsed >= 40
            assert elapsed < 1000
    
    def test_nested_budgets(self):
        """Test nested budget contexts."""
        with TimeoutBudget(max_duration_ms=1000) as parent:
            time.sleep(0.02)
            with TimeoutBudget(max_duration_ms=500) as child:
                time.sleep(0.02)
                assert child.elapsed_ms < parent.elapsed_ms


class TestWithTimeoutDecorator:
    """Tests for the with_timeout decorator."""
    
    def test_successful_function(self):
        """Test that fast functions complete successfully."""
        @with_timeout(timeout_ms=1000)
        def fast_function():
            return "success"
        
        result = fast_function()
        assert result == "success"
    
    def test_timeout_on_slow_function(self):
        """Test that slow functions raise TimeoutExceededError."""
        @with_timeout(timeout_ms=50)
        def slow_function():
            time.sleep(0.2)
            return "done"
        
        with pytest.raises(TimeoutExceededError):
            slow_function()
    
    def test_timeout_with_result(self):
        """Test that successful timeout returns result."""
        @with_timeout(timeout_ms=1000, on_timeout="return_none")
        def quick_function():
            return 42
        
        result = quick_function()
        assert result == 42


class TestBudgetCategory:
    """Tests for budget categories."""
    
    def test_category_creation(self):
        """Test creating budget categories."""
        category = BudgetCategory("network_requests", 5000)
        assert category.name == "network_requests"
        assert category.total_budget_ms == 5000
        assert category.allocated_ms == 0
    
    def test_category_allocation(self):
        """Test allocating budgets to categories."""
        category = BudgetCategory("api_calls", 1000)
        budget = category.allocate(200)
        assert budget.max_duration_ms == 200
        assert category.allocated_ms == 200
        
        budget2 = category.allocate(300)
        assert budget2.max_duration_ms == 300
        assert category.allocated_ms == 500


class TestBudgetMonitor:
    """Tests for the global budget monitor."""
    
    def test_monitor_singleton(self):
        """Test that get_global_monitor returns same instance."""
        monitor1 = get_global_monitor()
        monitor2 = get_global_monitor()
        assert monitor1 is monitor2
    
    def test_monitor_category_registration(self):
        """Test registering budget categories."""
        monitor = get_global_monitor()
        category = BudgetCategory("test_category", 1000)
        monitor.register_category(category)
        retrieved = monitor.get_category("test_category")
        assert retrieved is category
    
    def test_monitor_allocation(self):
        """Test allocating from monitor."""
        monitor = get_global_monitor()
        category = BudgetCategory("monitor_test", 500)
        monitor.register_category(category)
        budget = monitor.allocate("monitor_test", 100)
        assert budget.max_duration_ms == 100
        assert category.allocated_ms == 100


class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_zero_timeout(self):
        """Test handling of zero timeout."""
        tb = TimeoutBudget(max_duration_ms=0)
        assert tb.is_exhausted
    
    def test_negative_timeout_raises(self):
        """Test that negative timeout raises ValueError."""
        with pytest.raises(ValueError):
            TimeoutBudget(max_duration_ms=-100)
    
    def test_multiple_timeouts_same_budget(self):
        """Test using same budget for multiple timeouts."""
        tb = TimeoutBudget(max_duration_ms=100)
        with pytest.raises(TimeoutExceededError):
            with tb:
                time.sleep(0.2)
        assert tb.is_exhausted


class TestDecoratorOptions:
    """Tests for decorator configuration options."""
    
    def test_custom_timeout_value(self):
        """Test decorator with custom timeout value."""
        @with_timeout(timeout_ms=200, on_timeout="return_value", timeout_value="custom_timeout")
        def slow_func():
            time.sleep(0.3)
            return "done"
        
        result = slow_func()
        assert result == "custom_timeout"
    
    def test_reraise_option(self):
        """Test decorator with reraise=True."""
        @with_timeout(timeout_ms=50, on_timeout="reraise")
        def slow_func():
            time.sleep(0.2)
            return "done"
        
        with pytest.raises(TimeoutExceededError):
            slow_func()
    
    def test_none_on_timeout(self):
        """Test decorator returning None on timeout."""
        @with_timeout(timeout_ms=50, on_timeout="return_none")
        def slow_func():
            time.sleep(0.2)
            return "done"
        
        result = slow_func()
        assert result is None


class TestPerformanceCharacteristics:
    """Tests for performance and timing accuracy."""
    
    def test_timeout_accuracy(self):
        """Test that timeouts trigger at approximately the right time."""
        @with_timeout(timeout_ms=100, on_timeout="return_none")
        def measure_accuracy():
            time.sleep(0.2)
            return "not timeout"
        
        start = time.time()
        result = measure_accuracy()
        elapsed = (time.time() - start) * 1000
        
        assert result is None
        assert elapsed < 300
        assert elapsed >= 90
    
    def test_budget_efficiency(self):
        """Test that budgets don't add significant overhead."""
        tb = TimeoutBudget(max_duration_ms=10000)
        iterations = 1000
        start = time.time()
        for _ in range(iterations):
            _ = tb.remaining_ms
        elapsed = (time.time() - start) * 1000
        assert elapsed < 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
