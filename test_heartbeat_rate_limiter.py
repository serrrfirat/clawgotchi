"""
Test suite for Heartbeat Rate Limiter
Inspired by JonPJ's heartbeat hygiene pattern: https://www.moltbook.com/p/bd34f0aa
"""
import pytest
import os
import time
import json
from pathlib import Path

# Import the module to test
from heartbeat_rate_limiter import HeartbeatRateLimiter, RateLimitConfig


class TestRateLimitConfig:
    """Tests for RateLimitConfig class"""

    def test_default_config(self):
        """Default configuration should have sensible values"""
        config = RateLimitConfig()
        assert config.min_interval_seconds == 300  # 5 minutes
        assert config.checkpoints_dir == ".heartbeat_checkpoints"
        assert config.enabled is True

    def test_custom_config(self):
        """Custom configuration should accept all parameters"""
        config = RateLimitConfig(
            min_interval_seconds=600,
            checkpoints_dir="/tmp/test_checks",
            enabled=False
        )
        assert config.min_interval_seconds == 600
        assert config.checkpoints_dir == "/tmp/test_checks"
        assert config.enabled is False


class TestHeartbeatRateLimiter:
    """Tests for HeartbeatRateLimiter class"""

    @pytest.fixture
    def temp_checkpoints_dir(self, tmp_path):
        """Create a temporary directory for checkpoints"""
        checkpoints_dir = tmp_path / "checkpoints"
        checkpoints_dir.mkdir()
        return str(checkpoints_dir)

    @pytest.fixture
    def limiter(self, temp_checkpoints_dir):
        """Create a limiter instance with temp directory"""
        config = RateLimitConfig(
            min_interval_seconds=1,  # Short interval for testing
            checkpoints_dir=temp_checkpoints_dir
        )
        return HeartbeatRateLimiter(config=config)

    def test_initial_state(self, limiter):
        """New limiter should report as allowed (no previous checks)"""
        assert limiter.can_check() is True
        assert limiter.get_time_until_next_check() == 0

    def test_first_check_records_timestamp(self, limiter):
        """Recording a check should store the current timestamp"""
        result = limiter.record_check()
        assert result["success"] is True
        assert "timestamp" in result
        assert result["was_allowed"] is True

    def test_rate_limit_blocks_rapid_checks(self, limiter):
        """Rapid checks should be blocked by rate limiter"""
        # First check should succeed
        result1 = limiter.record_check()
        assert result1["success"] is True

        # Immediate second check should be blocked
        result2 = limiter.record_check()
        assert result2["success"] is False
        assert result2["was_allowed"] is False
        assert "rate limited" in result2["reason"].lower()

    def test_wait_time_after_check(self, limiter):
        """Should report correct wait time after a check"""
        limiter.record_check()
        wait_time = limiter.get_time_until_next_check()
        # Should be approximately 1 second (our min_interval_seconds)
        assert wait_time >= 0
        assert wait_time <= 2  # Allow some tolerance

    def test_get_last_check_timestamp_none(self, limiter):
        """Should return None for no previous check"""
        timestamp = limiter.get_last_check_timestamp()
        assert timestamp is None

    def test_get_last_check_timestamp_after_record(self, limiter):
        """Should return timestamp after recording a check"""
        limiter.record_check()
        timestamp = limiter.get_last_check_timestamp()
        assert timestamp is not None
        assert isinstance(timestamp, (int, float))

    def test_disabled_config_always_allows(self, temp_checkpoints_dir):
        """Disabled config should always allow checks"""
        config = RateLimitConfig(
            min_interval_seconds=3600,  # Very long
            checkpoints_dir=temp_checkpoints_dir,
            enabled=False
        )
        limiter = HeartbeatRateLimiter(config=config)

        # Should always allow checks when disabled
        result1 = limiter.record_check()
        result2 = limiter.record_check()
        
        assert result1["success"] is True
        assert result2["success"] is True

    def test_checkpoints_persistence(self, temp_checkpoints_dir):
        """Checkpoints should persist across limiter instances"""
        config = RateLimitConfig(
            min_interval_seconds=1,
            checkpoints_dir=temp_checkpoints_dir
        )
        
        # First instance: record a check
        limiter1 = HeartbeatRateLimiter(config=config)
        limiter1.record_check()
        timestamp1 = limiter1.get_last_check_timestamp()
        
        # Second instance: should see the persisted timestamp
        limiter2 = HeartbeatRateLimiter(config=config)
        timestamp2 = limiter2.get_last_check_timestamp()
        
        assert timestamp1 == timestamp2
        # Should be rate limited now
        assert limiter2.can_check() is False

    def test_get_rate_limit_status(self, limiter):
        """Should return comprehensive status dict"""
        status = limiter.get_rate_limit_status()
        
        assert "enabled" in status
        assert "min_interval_seconds" in status
        assert "last_check_timestamp" in status
        assert "can_check" in status
        assert "time_until_next_check" in status

    def test_wait_and_retry(self, limiter):
        """After waiting, should allow checks again"""
        # First check
        limiter.record_check()
        
        # Wait for rate limit to expire
        time.sleep(1.1)  # Slightly more than min_interval_seconds
        
        # Should be allowed now
        assert limiter.can_check() is True
        
        # Record should succeed
        result = limiter.record_check()
        assert result["success"] is True

    def test_reset_functionality(self, limiter):
        """Reset should clear the last check timestamp"""
        limiter.record_check()
        assert limiter.get_last_check_timestamp() is not None
        
        limiter.reset()
        assert limiter.get_last_check_timestamp() is None
        assert limiter.can_check() is True


class TestHeartbeatRateLimiterEdgeCases:
    """Edge case tests"""

    @pytest.fixture
    def temp_checkpoints_dir(self, tmp_path):
        """Create a temporary directory for checkpoints"""
        checkpoints_dir = tmp_path / "edge_cases"
        checkpoints_dir.mkdir()
        return str(checkpoints_dir)

    def test_corrupted_checkpoint_recovery(self, temp_checkpoints_dir):
        """Should recover from corrupted checkpoint file"""
        config = RateLimitConfig(
            min_interval_seconds=1,
            checkpoints_dir=temp_checkpoints_dir
        )
        
        # Corrupt the checkpoint file
        checkpoint_file = Path(temp_checkpoints_dir) / "last_check.json"
        with open(checkpoint_file, 'w') as f:
            f.write("this is not valid json {{{")
        
        # Limiter should handle this gracefully
        limiter = HeartbeatRateLimiter(config=config)
        # Should either recover or treat as no previous check
        assert limiter.can_check() is True or limiter.get_last_check_timestamp() is None

    def test_missing_checkpoint_directory(self, tmp_path):
        """Should create directory if it doesn't exist"""
        checkpoints_dir = str(tmp_path / "new_dir_that_does_not_exist")
        config = RateLimitConfig(
            min_interval_seconds=1,
            checkpoints_dir=checkpoints_dir
        )
        
        # Should not raise an error
        limiter = HeartbeatRateLimiter(config=config)
        assert Path(checkpoints_dir).exists()
