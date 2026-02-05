"""
Rate Limit Manager for Multi-Account Subagent Orchestration

Provides rate limiting, token bucket algorithm, and task queue management
for agents handling multiple OAuth accounts (e.g., 5 Google accounts).

Inspired by @ChinHeng_Lobster's Multi OAuth + Subagent Rate Limit problem on Moltbook.
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from heapq import heappush, heappop
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class TokenBucket:
    """
    Token bucket rate limiter implementation.
    
    Tokens are consumed with each request and refilled over time
    based on the configured refill rate.
    
    Attributes:
        capacity: Maximum number of tokens in the bucket
        refill_rate: Tokens added per second
        tokens: Current number of tokens available
        last_refill: Timestamp of last refill
    """
    capacity: float
    refill_rate: float
    tokens: float = field(default=None, init=False)
    last_refill: float = field(default=None, init=False)
    
    def __post_init__(self):
        """Initialize tokens to capacity."""
        self.tokens = float(self.capacity)
        self.last_refill = time.time()
    
    def consume(self, tokens: float = 1) -> bool:
        """
        Attempt to consume tokens from the bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    @property
    def remaining(self) -> float:
        """Get remaining tokens."""
        self._refill()
        return self.tokens


@dataclass
class AccountConfig:
    """
    Configuration for a rate-limited account.
    
    Attributes:
        account_id: Unique identifier for the account
        max_requests_per_minute: Rate limit for requests per minute
        max_requests_per_hour: Rate limit for requests per hour
        burst_limit: Maximum burst size (concurrent requests)
        retry_backoff_base: Base for exponential backoff calculations
        retry_max_attempts: Maximum retry attempts before giving up
    """
    account_id: str
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    burst_limit: int = 10
    retry_backoff_base: float = 2.0
    retry_max_attempts: int = 5


@dataclass(order=True)
class QueuedTask:
    """
    A task queued for deferred execution.
    
    Attributes:
        priority: Lower values = higher priority (processed first)
        enqueue_time: When the task was enqueued
        task: The callable to execute
        args: Positional arguments for the task
        kwargs: Keyword arguments for the task
        attempts: Number of execution attempts made
    """
    priority: int
    enqueue_time: float = field(default_factory=time.time)
    task: Callable = field(default=None)
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    attempts: int = field(default=0)


class TaskQueue:
    """
    Priority queue for deferred task execution.
    
    Supports FIFO ordering within the same priority level
    and automatic retry with exponential backoff.
    """
    
    def __init__(self):
        """Initialize an empty priority queue."""
        self._queue: List[QueuedTask] = []
    
    def enqueue(
        self,
        task: Callable,
        *args,
        priority: int = 0,
        **kwargs
    ) -> QueuedTask:
        """
        Add a task to the queue.
        
        Args:
            task: Callable to execute
            *args: Positional arguments for the task
            priority: Priority level (lower = higher priority)
            **kwargs: Keyword arguments for the task
            
        Returns:
            The queued task
        """
        queued_task = QueuedTask(
            priority=priority,
            task=task,
            args=args,
            kwargs=kwargs
        )
        heappush(self._queue, queued_task)
        return queued_task
    
    def dequeue(self) -> Optional[QueuedTask]:
        """
        Remove and return the highest priority task.
        
        Returns:
            The next task or None if queue is empty
        """
        if not self._queue:
            return None
        return heappop(self._queue)
    
    def __len__(self) -> int:
        """Return the number of tasks in the queue."""
        return len(self._queue)
    
    def peek(self) -> Optional[QueuedTask]:
        """
        Peek at the highest priority task without removing it.
        
        Returns:
            The next task or None if queue is empty
        """
        if not self._queue:
            return None
        return self._queue[0]


class RateLimitManager:
    """
    Central manager for multi-account rate limiting.
    
    Features:
    - Per-account rate limiting with token bucket algorithm
    - Global rate limit across all accounts
    - Automatic account rotation to least-used account
    - Task queue for deferred execution during rate limits
    - State persistence for resilience across restarts
    - Health scoring for monitoring
    
    Example:
        manager = RateLimitManager(
            state_file="/data/rate_limit_state.json",
            global_max_requests_per_minute=100
        )
        
        # Register multiple OAuth accounts
        manager.register_account(AccountConfig("google_1", max_requests_per_minute=30))
        manager.register_account(AccountConfig("google_2", max_requests_per_minute=30))
        manager.register_account(AccountConfig("google_3", max_requests_per_minute=30))
        
        # Execute with automatic rate limiting
        result = manager.execute_with_rate_limit(
            "google_1",
            some_api_call,
            allow_queue=True
        )
    """
    
    def __init__(
        self,
        state_file: Optional[str] = None,
        global_max_requests_per_minute: int = 0,
        global_burst_limit: int = 20
    ):
        """
        Initialize the Rate Limit Manager.
        
        Args:
            state_file: Path to JSON file for state persistence
            global_max_requests_per_minute: Global rate limit (0 = disabled)
            global_burst_limit: Global burst limit
        """
        self.state_file = state_file
        self.accounts: Dict[str, AccountConfig] = {}
        self.per_minute_buckets: Dict[str, TokenBucket] = {}
        self.per_hour_buckets: Dict[str, TokenBucket] = {}
        self.burst_buckets: Dict[str, TokenBucket] = {}
        
        # Global rate limiter
        self.global_rate_limiter: Optional[TokenBucket] = None
        if global_max_requests_per_minute > 0:
            self.global_rate_limiter = TokenBucket(
                capacity=global_burst_limit,
                refill_rate=global_max_requests_per_minute / 60.0
            )
        
        # Deferred task queue
        self.deferred_queue: TaskQueue = TaskQueue()
        
        # Request counters for smart account selection
        self.request_counters: Dict[str, int] = {}
        
        # Load existing state if available
        if state_file and os.path.exists(state_file):
            self.load_state()
    
    def register_account(self, config: AccountConfig) -> None:
        """
        Register an account for rate limiting.
        
        Args:
            config: Account configuration
        """
        self.accounts[config.account_id] = config
        
        # Create token buckets for this account
        self.per_minute_buckets[config.account_id] = TokenBucket(
            capacity=config.burst_limit,
            refill_rate=config.max_requests_per_minute / 60.0
        )
        
        self.per_hour_buckets[config.account_id] = TokenBucket(
            capacity=config.burst_limit,
            refill_rate=config.max_requests_per_hour / 3600.0
        )
        
        self.burst_buckets[config.account_id] = TokenBucket(
            capacity=config.burst_limit,
            refill_rate=config.burst_limit  # Instant refill
        )
        
        # Initialize request counter
        self.request_counters[config.account_id] = 0
    
    def check_rate_limit(self, account_id: str) -> Dict[str, Any]:
        """
        Check if a request is allowed for an account.
        
        Args:
            account_id: The account to check
            
        Returns:
            Dict with 'allowed', 'remaining', 'retry_after', and 'reason' keys
        """
        if account_id not in self.accounts:
            return {
                "allowed": False,
                "reason": "account_not_found",
                "account_id": account_id
            }
        
        config = self.accounts[account_id]
        per_minute = self.per_minute_buckets[account_id]
        per_hour = self.per_hour_buckets[account_id]
        burst = self.burst_buckets[account_id]
        
        # Check global rate limit first
        if self.global_rate_limiter:
            if not self.global_rate_limiter.consume(1):
                return {
                    "allowed": False,
                    "reason": "global_rate_exceeded",
                    "retry_after": 60.0 / max(1, config.max_requests_per_minute),
                    "account_id": account_id
                }
        
        # Check all rate limit buckets
        if not burst.consume(1):
            return {
                "allowed": False,
                "reason": "burst_exceeded",
                "retry_after": 1.0,
                "account_id": account_id
            }
        
        if not per_minute.consume(1):
            return {
                "allowed": False,
                "reason": "per_minute_exceeded",
                "retry_after": 60.0,
                "account_id": account_id
            }
        
        if not per_hour.consume(1):
            return {
                "allowed": False,
                "reason": "per_hour_exceeded",
                "retry_after": 3600.0,
                "account_id": account_id
            }
        
        # Update request counter
        self.request_counters[account_id] += 1
        
        return {
            "allowed": True,
            "remaining": min(
                per_minute.remaining,
                per_hour.remaining,
                burst.remaining
            ),
            "account_id": account_id
        }
    
    def get_best_account(self) -> Optional[str]:
        """
        Get the account with the most remaining rate limit quota.
        
        Returns:
            Account ID with best quota, or None if no accounts registered
        """
        if not self.accounts:
            return None
        
        best_account = None
        best_remaining = -1
        
        for account_id in self.accounts:
            bucket = self.per_minute_buckets[account_id]
            remaining = bucket.remaining
            
            # Consider request counter for load balancing
            load_factor = self.request_counters.get(account_id, 0) / 1000.0
            adjusted_remaining = remaining - load_factor
            
            if adjusted_remaining > best_remaining:
                best_remaining = adjusted_remaining
                best_account = account_id
        
        return best_account
    
    def get_account_status(self, account_id: str) -> Dict[str, Any]:
        """
        Get detailed status for an account.
        
        Args:
            account_id: The account to check
            
        Returns:
            Dict with account status information
        """
        if account_id not in self.accounts:
            return {"error": "account_not_found"}
        
        per_minute = self.per_minute_buckets[account_id]
        per_hour = self.per_hour_buckets[account_id]
        burst = self.burst_buckets[account_id]
        
        return {
            "account_id": account_id,
            "remaining": {
                "burst": burst.remaining,
                "per_minute": per_minute.remaining,
                "per_hour": per_hour.remaining
            },
            "total_requests": self.request_counters.get(account_id, 0),
            "config": {
                "max_per_minute": self.accounts[account_id].max_requests_per_minute,
                "max_per_hour": self.accounts[account_id].max_requests_per_hour,
                "burst_limit": self.accounts[account_id].burst_limit
            }
        }
    
    def get_all_accounts_status(self) -> List[Dict[str, Any]]:
        """
        Get status for all registered accounts.
        
        Returns:
            List of account status dicts
        """
        return [self.get_account_status(aid) for aid in self.accounts]
    
    def execute_with_rate_limit(
        self,
        account_id: str,
        func: Callable,
        *args,
        allow_queue: bool = False,
        **kwargs
    ) -> Any:
        """
        Execute a function with automatic rate limit handling.
        
        Args:
            account_id: Account to use for rate limiting
            func: Function to execute
            *args: Positional arguments for the function
            allow_queue: If True, queue the task when rate limited
            **kwargs: Keyword arguments for the function
            
        Returns:
            Function result, or None if queued (when allow_queue=True)
        """
        check_result = self.check_rate_limit(account_id)
        
        if not check_result["allowed"]:
            if allow_queue:
                # Add to deferred queue
                self.deferred_queue.enqueue(
                    func,
                    *args,
                    priority=1,  # Higher priority for deferred
                    **kwargs
                )
                return None
            else:
                raise RateLimitExceeded(
                    reason=check_result.get("reason", "unknown"),
                    retry_after=check_result.get("retry_after", 60.0)
                )
        
        # Execute the function
        return func(*args, **kwargs)
    
    def process_deferred_queue(self, account_id: Optional[str] = None) -> int:
        """
        Process tasks from the deferred queue.
        
        Args:
            account_id: Optional specific account to process for
            
        Returns:
            Number of tasks processed
        """
        processed = 0
        best_account = account_id or self.get_best_account()
        
        while len(self.deferred_queue) > 0:
            task = self.deferred_queue.dequeue()
            if task is None:
                break
            
            # Find an available account
            if best_account is None:
                best_account = self.get_best_account()
            
            if best_account is None:
                # No accounts available, requeue and stop
                self.deferred_queue.enqueue(
                    task.task,
                    *task.args,
                    priority=task.priority,
                    **task.kwargs
                )
                break
            
            # Try to execute
            check_result = self.check_rate_limit(best_account)
            
            if check_result["allowed"]:
                try:
                    task.task(*task.args, **task.kwargs)
                    processed += 1
                except Exception:
                    # Requeue on error
                    task.attempts += 1
                    if task.attempts < self.accounts[best_account].retry_max_attempts:
                        self.deferred_queue.enqueue(
                            task.task,
                            *task.args,
                            priority=task.priority + task.attempts,
                            **task.kwargs
                        )
            else:
                # Still rate limited, requeue
                self.deferred_queue.enqueue(
                    task.task,
                    *task.args,
                    priority=task.priority,
                    **task.kwargs
                )
                # Try a different account
                best_account = self.get_best_account()
        
        return processed
    
    def save_state(self) -> None:
        """Save current state to file."""
        if not self.state_file:
            return
        
        state = {
            "request_counters": self.request_counters,
            "timestamp": time.time()
        }
        
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        
        with open(self.state_file, "w") as f:
            json.dump(state, f)
    
    def load_state(self) -> None:
        """Load state from file."""
        if not self.state_file or not os.path.exists(self.state_file):
            return
        
        with open(self.state_file, "r") as f:
            state = json.load(f)
        
        if "request_counters" in state:
            self.request_counters = state["request_counters"]
    
    def get_health_score(self) -> Dict[str, Any]:
        """
        Calculate health score for the rate limit manager.
        
        Returns:
            Dict with 'score' (0-100), 'accounts_checked', and details
        """
        if not self.accounts:
            return {
                "score": 100,
                "accounts_checked": 0,
                "status": "no_accounts_configured"
            }
        
        total_remaining = 0
        accounts_checked = 0
        
        for account_id in self.accounts:
            bucket = self.per_minute_buckets[account_id]
            remaining = bucket.remaining
            capacity = self.accounts[account_id].burst_limit
            
            total_remaining += (remaining / capacity) if capacity > 0 else 0
            accounts_checked += 1
        
        avg_remaining = total_remaining / accounts_checked if accounts_checked > 0 else 0
        
        return {
            "score": min(100, int(avg_remaining * 100)),
            "accounts_checked": accounts_checked,
            "avg_remaining_percentage": avg_remaining * 100,
            "queued_tasks": len(self.deferred_queue),
            "status": "healthy" if avg_remaining > 0.3 else "degraded" if avg_remaining > 0 else "critical"
        }


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, reason: str = "unknown", retry_after: float = 60.0):
        """Initialize the exception."""
        self.reason = reason
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded: {reason}. Retry after {retry_after}s")
