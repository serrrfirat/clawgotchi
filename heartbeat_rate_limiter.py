"""
Heartbeat Rate Limiter

A utility for rate-limiting autonomous agent heartbeat checks.
Inspired by JonPJ's heartbeat hygiene pattern:
https://www.moltbook.com/p/bd34f0aa

Features:
- Configurable minimum interval between checks
- Persistent checkpoint storage for crash recovery
- Automatic state recovery from last known good state
- Rate limit status reporting
"""
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RateLimitConfig:
    """Configuration for HeartbeatRateLimiter
    
    Attributes:
        min_interval_seconds: Minimum seconds between allowed checks
        checkpoints_dir: Directory for persisting checkpoint state
        enabled: Whether rate limiting is enabled
    """
    min_interval_seconds: int = 300  # 5 minutes default
    checkpoints_dir: str = ".heartbeat_checkpoints"
    enabled: bool = True


class HeartbeatRateLimiter:
    """
    Rate limiter for autonomous agent heartbeat operations.
    
    Prevents over-polling of external services (like Moltbook)
    by enforcing a minimum interval between heartbeat checks.
    
    Usage:
        limiter = HeartbeatRateLimiter()
        if limiter.can_check():
            result = limiter.record_check()
            # Perform heartbeat operation...
    """
    
    CHECKPOINT_FILENAME = "last_check.json"
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize the rate limiter.
        
        Args:
            config: Optional RateLimitConfig. If not provided, uses defaults.
        """
        self.config = config or RateLimitConfig()
        self._checkpoints_dir = Path(self.config.checkpoints_dir)
        self._checkpoint_file = self._checkpoints_dir / self.CHECKPOINT_FILENAME
        self._ensure_checkpoint_dir()
        self._last_timestamp: Optional[float] = self._load_checkpoint()
    
    def can_check(self) -> bool:
        """
        Check if a new heartbeat check is allowed.
        
        Returns:
            True if allowed, False if rate limited or disabled.
        """
        if not self.config.enabled:
            return True
        
        if self._last_timestamp is None:
            return True
        
        elapsed = time.time() - self._last_timestamp
        return elapsed >= self.config.min_interval_seconds
    
    def get_time_until_next_check(self) -> float:
        """
        Get seconds until the next check is allowed.
        
        Returns:
            Number of seconds to wait. 0 if allowed now or no previous check.
        """
        if self._last_timestamp is None:
            return 0
        
        elapsed = time.time() - self._last_timestamp
        remaining = self.config.min_interval_seconds - elapsed
        return max(0, remaining)
    
    def record_check(self) -> dict:
        """
        Record a heartbeat check attempt.
        
        Returns:
            Dict with keys:
                - success: bool (whether check was allowed)
                - was_allowed: bool (whether check passed rate limit)
                - timestamp: float (current timestamp)
                - reason: str (explanation if blocked)
        """
        allowed = self.can_check()
        current_time = time.time()
        
        if allowed:
            self._last_timestamp = current_time
            self._save_checkpoint(current_time)
            
            return {
                "success": True,
                "was_allowed": True,
                "timestamp": current_time,
                "reason": "check allowed"
            }
        else:
            wait_time = self.get_time_until_next_check()
            return {
                "success": False,
                "was_allowed": False,
                "timestamp": current_time,
                "reason": f"rate limited - wait {wait_time:.1f} seconds"
            }
    
    def get_last_check_timestamp(self) -> Optional[float]:
        """
        Get the timestamp of the last recorded check.
        
        Returns:
            Unix timestamp or None if no previous check.
        """
        return self._last_timestamp
    
    def get_rate_limit_status(self) -> dict:
        """
        Get comprehensive rate limit status.
        
        Returns:
            Dict with:
                - enabled: bool
                - min_interval_seconds: int
                - last_check_timestamp: Optional[float]
                - can_check: bool
                - time_until_next_check: float
        """
        return {
            "enabled": self.config.enabled,
            "min_interval_seconds": self.config.min_interval_seconds,
            "last_check_timestamp": self._last_timestamp,
            "can_check": self.can_check(),
            "time_until_next_check": self.get_time_until_next_check()
        }
    
    def reset(self):
        """Reset the rate limiter state (clear last check timestamp)."""
        self._last_timestamp = None
        if self._checkpoint_file.exists():
            self._checkpoint_file.unlink()
    
    def _ensure_checkpoint_dir(self):
        """Ensure the checkpoints directory exists."""
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    def _save_checkpoint(self, timestamp: float):
        """Save checkpoint to persistent storage."""
        data = {
            "timestamp": timestamp,
            "min_interval_seconds": self.config.min_interval_seconds
        }
        with open(self._checkpoint_file, 'w') as f:
            json.dump(data, f)
    
    def _load_checkpoint(self) -> Optional[float]:
        """Load checkpoint from persistent storage."""
        if not self._checkpoint_file.exists():
            return None
        
        try:
            with open(self._checkpoint_file, 'r') as f:
                data = json.load(f)
            
            # Verify config hasn't changed significantly
            if data.get("min_interval_seconds") != self.config.min_interval_seconds:
                # Config changed - reset state
                return None
            
            return data.get("timestamp")
        except (json.JSONDecodeError, KeyError, OSError):
            # Corrupted or invalid checkpoint - treat as no previous check
            return None


# Convenience function for quick setup
def create_limiter(
    min_interval_seconds: int = 300,
    checkpoints_dir: str = ".heartbeat_checkpoints",
    enabled: bool = True
) -> HeartbeatRateLimiter:
    """
    Create a HeartbeatRateLimiter with common defaults.
    
    Args:
        min_interval_seconds: Minimum seconds between checks (default: 5 min)
        checkpoints_dir: Directory for checkpoints
        enabled: Whether rate limiting is enabled
    
    Returns:
        Configured HeartbeatRateLimiter instance
    """
    config = RateLimitConfig(
        min_interval_seconds=min_interval_seconds,
        checkpoints_dir=checkpoints_dir,
        enabled=enabled
    )
    return HeartbeatRateLimiter(config=config)
