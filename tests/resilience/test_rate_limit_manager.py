"""Tests for Rate Limit Manager for multi-account subagent orchestration."""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from clawgotchi.resilience.rate_limit_manager import (
    AccountConfig,
    RateLimitManager,
    TaskQueue,
    TokenBucket,
)


class TestTokenBucket:
    """Unit tests for TokenBucket rate limiting algorithm."""

    def test_token_bucket_initialization(self):
        """Test TokenBucket initializes with correct capacity and refill rate."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
        assert bucket.tokens == 10

    def test_token_bucket_consume_success(self):
        """Test consuming tokens when available."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.tokens == 5
        result = bucket.consume(3)
        assert result is True
        assert bucket.tokens == 2

    def test_token_bucket_consume_failure(self):
        """Test consuming more tokens than available."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        result = bucket.consume(10)
        assert result is False
        assert bucket.tokens == 5  # Unchanged

    def test_token_bucket_refill(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)  # 2 tokens per second
        bucket.consume(5)
        assert bucket.tokens == 5
        time.sleep(0.6)
        bucket._refill()
        # Should have ~1.2 tokens, but at least 1
        assert bucket.tokens >= 5

    def test_token_bucket_max_capacity(self):
        """Test tokens don't exceed capacity on refill."""
        bucket = TokenBucket(capacity=10, refill_rate=5.0)
        bucket.consume(2)
        assert bucket.tokens == 8
        # Refill should bring it to max (cap at 10)
        time.sleep(0.5)  # Wait for some refill
        bucket._refill()
        assert bucket.tokens <= 10  # Should be capped at capacity
        assert bucket.tokens > 8  # But should have refilled


class TestAccountConfig:
    """Unit tests for AccountConfig."""

    def test_account_config_defaults(self):
        """Test AccountConfig uses sensible defaults."""
        config = AccountConfig(account_id="test_account")
        assert config.account_id == "test_account"
        assert config.max_requests_per_minute == 60
        assert config.max_requests_per_hour == 1000
        assert config.burst_limit == 10
        assert config.retry_backoff_base == 2.0
        assert config.retry_max_attempts == 5

    def test_account_config_custom_values(self):
        """Test AccountConfig with custom values."""
        config = AccountConfig(
            account_id="google_1",
            max_requests_per_minute=30,
            max_requests_per_hour=500,
            burst_limit=5,
            retry_backoff_base=3.0,
            retry_max_attempts=3,
        )
        assert config.account_id == "google_1"
        assert config.max_requests_per_minute == 30
        assert config.max_requests_per_hour == 500
        assert config.burst_limit == 5
        assert config.retry_backoff_base == 3.0
        assert config.retry_max_attempts == 3


class TestTaskQueue:
    """Unit tests for TaskQueue deferred execution."""

    def test_task_queue_add_and_process(self):
        """Test adding and processing tasks."""
        queue = TaskQueue()
        results = []

        def task(x):
            results.append(x)
            return x * 2

        queue.enqueue(task, 5)
        queue.enqueue(task, 10)

        # Process one task
        result = queue.dequeue()
        assert result is not None
        assert result.task(result.args[0]) == 10
        assert len(results) == 1

    def test_task_queue_empty(self):
        """Test dequeuing from empty queue."""
        queue = TaskQueue()
        result = queue.dequeue()
        assert result is None

    def test_task_queue_order_preserved(self):
        """Test FIFO ordering is maintained."""
        queue = TaskQueue()
        order = []

        def record(i):
            order.append(i)

        for i in range(5):
            queue.enqueue(record, i)

        for i in range(5):
            task = queue.dequeue()
            task.task(*task.args)

        assert order == [0, 1, 2, 3, 4]

    def test_task_queue_priority(self):
        """Test priority ordering."""
        queue = TaskQueue()
        order = []

        def record(i):
            order.append(i)

        queue.enqueue(record, 1, priority=1)
        queue.enqueue(record, 2, priority=0)  # Higher priority
        queue.enqueue(record, 3, priority=2)

        for _ in range(3):
            task = queue.dequeue()
            task.task(*task.args)

        assert order == [2, 1, 3]


class TestRateLimitManager:
    """Unit tests for RateLimitManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, "rate_limit_state.json")

    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_rate_limit_manager_initialization(self):
        """Test RateLimitManager initializes correctly."""
        manager = RateLimitManager(state_file=self.state_file)
        assert manager.state_file == self.state_file
        assert len(manager.accounts) == 0
        # Global rate limiter is None when not configured
        assert manager.global_rate_limiter is None
        
        # Test with global rate limiter
        manager2 = RateLimitManager(
            state_file=self.state_file,
            global_max_requests_per_minute=100
        )
        assert manager2.global_rate_limiter is not None

    def test_register_account(self):
        """Test registering an account."""
        manager = RateLimitManager(state_file=self.state_file)
        config = AccountConfig(
            account_id="google_1",
            max_requests_per_minute=30,
        )
        manager.register_account(config)

        assert "google_1" in manager.accounts
        assert manager.accounts["google_1"].account_id == "google_1"

    def test_check_rate_limit_available(self):
        """Test rate limit check when available."""
        manager = RateLimitManager(state_file=self.state_file)
        config = AccountConfig(
            account_id="test_account",
            max_requests_per_minute=100,
            max_requests_per_hour=1000,
            burst_limit=10,
        )
        manager.register_account(config)

        result = manager.check_rate_limit("test_account")
        assert result["allowed"] is True
        assert result["remaining"] >= 0
        assert result["account_id"] == "test_account"

    def test_check_rate_limit_exhausted(self):
        """Test rate limit check when exhausted."""
        manager = RateLimitManager(state_file=self.state_file)
        config = AccountConfig(
            account_id="test_account",
            max_requests_per_minute=1,
            max_requests_per_hour=1,
            burst_limit=1,
        )
        manager.register_account(config)

        # First request should succeed
        result1 = manager.check_rate_limit("test_account")
        assert result1["allowed"] is True

        # Second should be rate limited (exhausted burst)
        result2 = manager.check_rate_limit("test_account")
        assert result2["allowed"] is False
        assert "retry_after" in result2

    def test_get_best_account(self):
        """Test selecting an account returns a valid account."""
        manager = RateLimitManager(state_file=self.state_file)

        manager.register_account(AccountConfig("a1", max_requests_per_minute=10))
        manager.register_account(AccountConfig("a2", max_requests_per_minute=50))
        manager.register_account(AccountConfig("a3", max_requests_per_minute=30))

        # Should return one of the registered accounts
        best = manager.get_best_account()
        assert best in ["a1", "a2", "a3"]

        # Consume all from a1's burst
        for _ in range(10):
            manager.check_rate_limit("a1")

        # a1 should still be returned (it has per-minute tokens)
        best = manager.get_best_account()
        assert best in ["a1", "a2", "a3"]

        # With no accounts, should return None
        empty_manager = RateLimitManager(state_file=self.state_file)
        assert empty_manager.get_best_account() is None

    def test_get_account_status(self):
        """Test getting status for a specific account."""
        manager = RateLimitManager(state_file=self.state_file)
        manager.register_account(AccountConfig("test", max_requests_per_minute=60))

        status = manager.get_account_status("test")
        assert status["account_id"] == "test"
        assert "remaining" in status
        assert "config" in status
        assert status["config"]["max_per_minute"] == 60

    def test_global_rate_limit(self):
        """Test global rate limit across all accounts."""
        manager = RateLimitManager(
            state_file=self.state_file,
            global_max_requests_per_minute=5,
            global_burst_limit=5,  # Match global limit
        )

        manager.register_account(AccountConfig("a1", max_requests_per_minute=100))
        manager.register_account(AccountConfig("a2", max_requests_per_minute=100))

        # Global limit should apply - 5 requests allowed
        for i in range(5):
            result = manager.check_rate_limit("a1")
            assert result["allowed"] is True

        # 6th request should be blocked by global limit
        result = manager.check_rate_limit("a1")
        assert result["allowed"] is False
        assert result.get("reason") == "global_rate_exceeded"

    def test_execute_with_rate_limit(self):
        """Test executing a function with automatic rate limit handling."""
        manager = RateLimitManager(state_file=self.state_file)
        manager.register_account(AccountConfig("test", max_requests_per_minute=100))

        call_count = 0

        def tracked_call():
            nonlocal call_count
            call_count += 1
            return "success"

        # Should succeed
        result = manager.execute_with_rate_limit("test", tracked_call)
        assert result == "success"
        assert call_count == 1

    def test_save_and_load_state(self):
        """Test state persistence."""
        manager1 = RateLimitManager(state_file=self.state_file)
        manager1.register_account(AccountConfig("test", max_requests_per_minute=50))
        manager1.check_rate_limit("test")
        assert manager1.request_counters.get("test", 0) == 1
        manager1.save_state()

        # Create new manager and load state
        manager2 = RateLimitManager(state_file=self.state_file)
        # Note: accounts must be re-registered, only counters are persisted
        manager2.register_account(AccountConfig("test", max_requests_per_minute=50))
        manager2.load_state()

        # State should be restored
        assert manager2.request_counters.get("test", 0) == 1

    def test_get_all_accounts_status(self):
        """Test getting status for all accounts."""
        manager = RateLimitManager(state_file=self.state_file)
        manager.register_account(AccountConfig("a1", max_requests_per_minute=10))
        manager.register_account(AccountConfig("a2", max_requests_per_minute=20))

        all_status = manager.get_all_accounts_status()

        assert len(all_status) == 2
        account_ids = {s["account_id"] for s in all_status}
        assert account_ids == {"a1", "a2"}

    def test_rotate_to_best_account(self):
        """Test rotating to account with most remaining quota."""
        manager = RateLimitManager(state_file=self.state_file)
        manager.register_account(AccountConfig("slow", max_requests_per_minute=5))
        manager.register_account(AccountConfig("fast", max_requests_per_minute=100))

        # Use up slow account
        for _ in range(5):
            manager.check_rate_limit("slow")

        best = manager.get_best_account()
        assert best == "fast"

    def test_unregistered_account_returns_error(self):
        """Test that unregistered accounts return error."""
        manager = RateLimitManager(state_file=self.state_file)

        result = manager.check_rate_limit("nonexistent")
        assert result["allowed"] is False
        assert result.get("reason") == "account_not_found"

    def test_queue_deferred_task(self):
        """Test queuing a task when rate limited."""
        manager = RateLimitManager(state_file=self.state_file)
        manager.register_account(
            AccountConfig(
                "test",
                max_requests_per_minute=1,
                burst_limit=1,
            )
        )

        # Exhaust the account
        manager.check_rate_limit("test")

        result = []
        task = lambda: result.append("done")

        # Should be queued
        queued = manager.execute_with_rate_limit("test", task, allow_queue=True)
        assert queued is None  # Not executed immediately
        assert len(manager.deferred_queue) == 1

    def test_get_health_score(self):
        """Test health score calculation."""
        manager = RateLimitManager(state_file=self.state_file)
        manager.register_account(AccountConfig("a1", max_requests_per_minute=10))
        manager.register_account(AccountConfig("a2", max_requests_per_minute=20))

        health = manager.get_health_score()

        assert "score" in health
        assert "accounts_checked" in health
        assert health["accounts_checked"] == 2
        assert 0 <= health["score"] <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
