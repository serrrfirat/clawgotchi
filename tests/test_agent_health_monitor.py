"""
Tests for Agent Health Monitor.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add utils to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.agent_health_monitor import AgentHealthMonitor, HealthStatus


class TestAgentHealthMonitor(unittest.TestCase):
    """Test suite for AgentHealthMonitor."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, "test_health_state.json")
        self.monitor = AgentHealthMonitor(state_file=self.state_file)

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        os.rmdir(self.temp_dir)

    def test_initial_state(self):
        """Test that monitor initializes with empty metrics."""
        self.assertIsNone(self.monitor.start_time)
        self.assertEqual(self.monitor.metrics["cpu_percent"], [])
        self.assertEqual(self.monitor.metrics["memory_percent"], [])
        self.assertEqual(self.monitor.metrics["api_latency_ms"], [])
        self.assertEqual(self.monitor.metrics["error_count"], 0)
        self.assertEqual(self.monitor.metrics["success_count"], 0)

    def test_start_session(self):
        """Test starting a monitoring session."""
        self.monitor.start_session()

        self.assertIsNotNone(self.monitor.start_time)
        self.assertEqual(self.monitor.metrics["success_count"], 0)
        self.assertEqual(self.monitor.metrics["error_count"], 0)

    def test_record_cpu(self):
        """Test recording CPU usage."""
        self.monitor.record_cpu(45.5)

        self.assertEqual(len(self.monitor.metrics["cpu_percent"]), 1)
        self.assertEqual(self.monitor.metrics["cpu_percent"][0], 45.5)

    def test_record_memory(self):
        """Test recording memory usage."""
        self.monitor.record_memory(72.3)

        self.assertEqual(len(self.monitor.metrics["memory_percent"]), 1)
        self.assertEqual(self.monitor.metrics["memory_percent"][0], 72.3)

    def test_record_api_latency(self):
        """Test recording API latency."""
        self.monitor.record_api_latency(123.45)

        self.assertEqual(len(self.monitor.metrics["api_latency_ms"]), 1)
        self.assertEqual(self.monitor.metrics["api_latency_ms"][0], 123.45)

    def test_record_success(self):
        """Test recording a successful operation."""
        self.monitor.record_success()
        self.monitor.record_success()
        self.monitor.record_success()

        self.assertEqual(self.monitor.metrics["success_count"], 3)

    def test_record_error(self):
        """Test recording a failed operation."""
        self.monitor.record_error()
        self.monitor.record_error()

        self.assertEqual(self.monitor.metrics["error_count"], 2)

    def test_add_checkpoint(self):
        """Test adding a named checkpoint."""
        self.monitor.add_checkpoint("task_start", {"task": "build"})
        self.monitor.add_checkpoint("task_complete", {"task": "build", "result": "success"})

        self.assertEqual(len(self.monitor.metrics["checkpoints"]), 2)
        self.assertEqual(self.monitor.metrics["checkpoints"][0]["name"], "task_start")
        self.assertEqual(self.monitor.metrics["checkpoints"][1]["data"]["result"], "success")

    def test_history_limiting(self):
        """Test that history is limited to 60 entries."""
        # Add 70 CPU readings
        for i in range(70):
            self.monitor.record_cpu(i)

        # Should only have last 60
        self.assertEqual(len(self.monitor.metrics["cpu_percent"]), 60)
        self.assertEqual(self.monitor.metrics["cpu_percent"][0], 10)  # First 10 dropped
        self.assertEqual(self.monitor.metrics["cpu_percent"][-1], 69)  # Last one kept

    def test_check_health_no_psutil(self):
        """Test health check when psutil is not available."""
        with patch.dict('sys.modules', {'psutil': None}):
            # Reload module to test without psutil
            import importlib
            import utils.agent_health_monitor
            importlib.reload(utils.agent_health_monitor)

            # Create new instance without psutil
            monitor = utils.agent_health_monitor.AgentHealthMonitor(state_file=self.state_file)
            monitor.start_session()

            report = monitor.check_health()
            self.assertEqual(report["status"], HealthStatus.UNKNOWN.value)

    def test_check_health_healthy(self):
        """Test health check reports HEALTHY when metrics are good."""
        self.monitor.start_session()

        # Record good metrics
        self.monitor.record_cpu(30.0)
        self.monitor.record_memory(40.0)
        self.monitor.record_api_latency(100.0)
        self.monitor.record_success()
        self.monitor.record_success()
        self.monitor.record_success()

        report = self.monitor.check_health()
        self.assertEqual(report["status"], HealthStatus.HEALTHY.value)
        self.assertEqual(len(report["issues"]), 0)

    def test_check_health_degraded_high_cpu(self):
        """Test health check reports DEGRADED with high CPU."""
        self.monitor.start_session()

        # Record high CPU
        for _ in range(10):
            self.monitor.record_cpu(85.0)

        report = self.monitor.check_health()
        self.assertEqual(report["status"], HealthStatus.DEGRADED.value)
        self.assertTrue(any(i["type"] == "high_cpu" for i in report["issues"]))

    def test_check_health_critical(self):
        """Test health check reports CRITICAL with very high CPU."""
        self.monitor.start_session()

        # Record critical CPU
        for _ in range(10):
            self.monitor.record_cpu(96.0)

        report = self.monitor.check_health()
        self.assertEqual(report["status"], HealthStatus.CRITICAL.value)

    def test_check_health_degraded_high_memory(self):
        """Test health check reports DEGRADED with high memory."""
        self.monitor.start_session()

        # Record high memory
        for _ in range(10):
            self.monitor.record_memory(90.0)

        report = self.monitor.check_health()
        self.assertEqual(report["status"], HealthStatus.DEGRADED.value)
        self.assertTrue(any(i["type"] == "high_memory" for i in report["issues"]))

    def test_check_health_low_success_rate(self):
        """Test health check reports issue with low success rate."""
        self.monitor.start_session()

        # Record many errors
        for _ in range(15):
            self.monitor.record_success()
        for _ in range(5):
            self.monitor.record_error()

        report = self.monitor.check_health()
        self.assertTrue(any(i["type"] == "low_success_rate" for i in report["issues"]))
        self.assertEqual(report["operations"]["success_rate"], 75.0)

    def test_check_health_high_latency(self):
        """Test health check reports issue with high API latency."""
        self.monitor.start_session()

        # Record high latency
        for _ in range(10):
            self.monitor.record_api_latency(6000.0)

        report = self.monitor.check_health()
        self.assertTrue(any(i["type"] == "high_latency" for i in report["issues"]))

    def test_check_health_includes_uptime(self):
        """Test health check includes uptime calculation."""
        self.monitor.start_session()

        report = self.monitor.check_health()
        self.assertIsNotNone(report["uptime_seconds"])
        self.assertGreater(report["uptime_seconds"], 0)

    def test_check_health_includes_metrics(self):
        """Test health check includes all metrics."""
        self.monitor.start_session()
        self.monitor.record_cpu(50.0)
        self.monitor.record_memory(60.0)
        self.monitor.record_api_latency(200.0)

        report = self.monitor.check_health()

        self.assertIn("cpu_percent", report["metrics"])
        self.assertIn("memory_percent", report["metrics"])
        self.assertIn("api_latency_ms", report["metrics"])

        self.assertEqual(report["metrics"]["cpu_percent"]["current"], 50.0)
        self.assertEqual(report["metrics"]["memory_percent"]["current"], 60.0)

    def test_get_health_summary(self):
        """Test human-readable health summary."""
        self.monitor.start_session()
        self.monitor.record_cpu(25.0)
        self.monitor.record_memory(35.0)
        self.monitor.record_success()

        summary = self.monitor.get_health_summary()

        self.assertIn("Agent Health Report", summary)
        self.assertIn("Status:", summary)
        self.assertIn("CPU:", summary)
        self.assertIn("Memory:", summary)

    def test_is_healthy(self):
        """Test is_healthy returns correct boolean."""
        self.monitor.start_session()

        # Should be healthy with good metrics
        self.monitor.record_cpu(30.0)
        self.monitor.record_memory(40.0)
        self.assertTrue(self.monitor.is_healthy())

        # Should not be healthy with bad metrics
        for _ in range(10):
            self.monitor.record_cpu(90.0)
        self.assertFalse(self.monitor.is_healthy())

    def test_get_statistics(self):
        """Test get_statistics returns aggregated data."""
        self.monitor.start_session()
        self.monitor.record_cpu(30.0)
        self.monitor.record_cpu(40.0)
        self.monitor.record_cpu(50.0)
        self.monitor.record_memory(40.0)
        self.monitor.record_memory(50.0)
        self.monitor.record_memory(60.0)
        self.monitor.record_success()
        self.monitor.record_success()
        self.monitor.record_error()

        stats = self.monitor.get_statistics()

        self.assertIn("status", stats)
        self.assertIn("cpu_avg", stats)
        self.assertIn("memory_avg", stats)
        self.assertIn("success_rate", stats)
        self.assertEqual(stats["cpu_avg"], 40.0)
        self.assertEqual(stats["memory_avg"], 50.0)
        self.assertEqual(stats["success_rate"], 66.7)

    def test_persistence(self):
        """Test that state is saved and loaded correctly."""
        self.monitor.start_session()
        self.monitor.record_cpu(42.0)
        self.monitor.record_memory(58.0)
        self.monitor.record_success()
        self.monitor.record_error()

        # Create new monitor instance (simulating restart)
        monitor2 = AgentHealthMonitor(state_file=self.state_file)

        self.assertEqual(monitor2.metrics["cpu_percent"], [42.0])
        self.assertEqual(monitor2.metrics["memory_percent"], [58.0])
        self.assertEqual(monitor2.metrics["success_count"], 1)
        self.assertEqual(monitor2.metrics["error_count"], 1)


class TestHealthStatus(unittest.TestCase):
    """Test HealthStatus enum values."""

    def test_enum_values(self):
        """Test that enum has expected values."""
        self.assertEqual(HealthStatus.HEALTHY.value, "healthy")
        self.assertEqual(HealthStatus.DEGRADED.value, "degraded")
        self.assertEqual(HealthStatus.CRITICAL.value, "critical")
        self.assertEqual(HealthStatus.UNKNOWN.value, "unknown")


if __name__ == "__main__":
    unittest.main()
