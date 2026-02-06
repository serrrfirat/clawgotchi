"""
Agent Health Monitor - Self-diagnosing system health tracker.

Tracks CPU, memory, API latency, error rates, and provides
transparent health reporting for autonomous agents.
"""

import json
import os
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AgentHealthMonitor:
    """Self-diagnosing health monitor for autonomous agents."""

    def __init__(self, state_file: str = None):
        self.state_file = state_file or str(
            Path(__file__).parent / "agent_health_state.json"
        )
        self.metrics = {
            "cpu_percent": [],
            "memory_percent": [],
            "api_latency_ms": [],
            "error_count": 0,
            "success_count": 0,
            "start_time": None,
            "last_check": None,
            "checkpoints": [],
        }
        self.start_time = None
        self._load_state()

    def _load_state(self) -> None:
        """Load state from persistent storage."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    # Restore metrics history (limited to last 60 entries)
                    self.metrics = data.get("metrics", self.metrics)
                    self.start_time = data.get("start_time")
            except (json.JSONDecodeError, IOError):
                pass

    def _save_state(self) -> None:
        """Save state to persistent storage."""
        state = {
            "metrics": self.metrics,
            "start_time": self.start_time,
            "last_check": datetime.now().isoformat(),
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except IOError:
            pass  # Silently fail if we can't save

    def start_session(self) -> None:
        """Mark the start of a monitoring session."""
        self.start_time = datetime.now().isoformat()
        self.metrics = {
            "cpu_percent": [],
            "memory_percent": [],
            "api_latency_ms": [],
            "error_count": 0,
            "success_count": 0,
            "start_time": self.start_time,
            "last_check": datetime.now().isoformat(),
            "checkpoints": [],
        }
        self._save_state()

    def record_cpu(self, percent: float) -> None:
        """Record CPU usage percentage."""
        self.metrics["cpu_percent"].append(percent)
        self.metrics["cpu_percent"] = self.metrics["cpu_percent"][-60:]
        self.metrics["last_check"] = datetime.now().isoformat()
        self._save_state()

    def record_memory(self, percent: float) -> None:
        """Record memory usage percentage."""
        self.metrics["memory_percent"].append(percent)
        self.metrics["memory_percent"] = self.metrics["memory_percent"][-60:]
        self.metrics["last_check"] = datetime.now().isoformat()
        self._save_state()

    def record_api_latency(self, latency_ms: float) -> None:
        """Record API call latency in milliseconds."""
        self.metrics["api_latency_ms"].append(latency_ms)
        self.metrics["api_latency_ms"] = self.metrics["api_latency_ms"][-60:]
        self.metrics["last_check"] = datetime.now().isoformat()
        self._save_state()

    def record_success(self) -> None:
        """Record a successful operation."""
        self.metrics["success_count"] += 1
        self.metrics["last_check"] = datetime.now().isoformat()
        self._save_state()

    def record_error(self) -> None:
        """Record a failed operation."""
        self.metrics["error_count"] += 1
        self.metrics["last_check"] = datetime.now().isoformat()
        self._save_state()

    def add_checkpoint(self, name: str, data: dict = None) -> None:
        """Add a named checkpoint with optional data."""
        checkpoint = {
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "data": data or {},
        }
        self.metrics["checkpoints"].append(checkpoint)
        self.metrics["checkpoints"] = self.metrics["checkpoints"][-50:]
        self._save_state()

    def get_cpu_percent(self) -> float:
        """Get current CPU usage (mockable for testing)."""
        if HAS_PSUTIL:
            return psutil.cpu_percent(interval=0.1)
        return 0.0

    def get_memory_percent(self) -> float:
        """Get current memory usage (mockable for testing)."""
        if HAS_PSUTIL:
            return psutil.virtual_memory().percent
        return 0.0

    def check_health(self) -> dict:
        """
        Perform a comprehensive health check.

        Returns a transparent health report with:
        - status: HEALTHY, DEGRADED, CRITICAL, or UNKNOWN
        - metrics: current and historical metrics
        - uptime_seconds: how long the agent has been running
        - success_rate: percentage of successful operations
        - issues: list of detected issues (if any)
        """
        now = datetime.now()
        uptime_seconds = None
        if self.start_time:
            try:
                start = datetime.fromisoformat(self.start_time)
                uptime_seconds = (now - start).total_seconds()
            except (ValueError, TypeError):
                pass

        # Get current metrics
        cpu = self.get_cpu_percent()
        memory = self.get_memory_percent()

        self.record_cpu(cpu)
        self.record_memory(memory)

        # Calculate averages from history
        cpu_history = self.metrics["cpu_percent"]
        memory_history = self.metrics["memory_percent"]
        latency_history = self.metrics["api_latency_ms"]

        avg_cpu = sum(cpu_history) / len(cpu_history) if cpu_history else 0
        avg_memory = sum(memory_history) / len(memory_history) if memory_history else 0
        avg_latency = sum(latency_history) / len(latency_history) if latency_history else 0

        # Calculate success rate
        total_ops = self.metrics["success_count"] + self.metrics["error_count"]
        success_rate = (self.metrics["success_count"] / total_ops * 100) if total_ops > 0 else 100

        # Detect issues
        issues = []

        if avg_cpu > 80:
            issues.append({"type": "high_cpu", "message": f"CPU usage averaging {avg_cpu:.1f}%"})

        if avg_memory > 85:
            issues.append({"type": "high_memory", "message": f"Memory usage averaging {avg_memory:.1f}%"})

        if avg_latency > 5000 and latency_history:
            issues.append({"type": "high_latency", "message": f"API latency averaging {avg_latency:.0f}ms"})

        if success_rate < 90 and total_ops > 10:
            issues.append({"type": "low_success_rate", "message": f"Success rate at {success_rate:.1f}%"})

        # Determine overall status
        if not HAS_PSUTIL:
            status = HealthStatus.UNKNOWN
        elif issues:
            critical_count = sum(1 for i in issues if (
                i["type"] in ("high_cpu", "high_memory") and
                (avg_cpu > 95 or avg_memory > 95)
            ))
            if critical_count > 0:
                status = HealthStatus.CRITICAL
            else:
                status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return {
            "status": status.value,
            "timestamp": now.isoformat(),
            "uptime_seconds": uptime_seconds,
            "metrics": {
                "cpu_percent": {
                    "current": round(cpu, 1),
                    "average_60s": round(avg_cpu, 1),
                    "history_count": len(cpu_history),
                },
                "memory_percent": {
                    "current": round(memory, 1),
                    "average_60s": round(avg_memory, 1),
                    "history_count": len(memory_history),
                },
                "api_latency_ms": {
                    "average": round(avg_latency, 1) if avg_latency else None,
                    "history_count": len(latency_history),
                },
            },
            "operations": {
                "success": self.metrics["success_count"],
                "errors": self.metrics["error_count"],
                "success_rate": round(success_rate, 1),
            },
            "checkpoints": len(self.metrics["checkpoints"]),
            "issues": issues,
        }

    def get_health_summary(self) -> str:
        """Get a human-readable health summary."""
        report = self.check_health()
        status = report["status"].upper()

        lines = [
            f"🤖 Agent Health Report",
            f"   Status: {status}",
            f"   Uptime: {report['uptime_seconds']:.0f}s" if report['uptime_seconds'] else "   Uptime: unknown",
            f"   CPU: {report['metrics']['cpu_percent']['current']}% (avg: {report['metrics']['cpu_percent']['average_60s']}%)",
            f"   Memory: {report['metrics']['memory_percent']['current']}% (avg: {report['metrics']['memory_percent']['average_60s']}%)",
            f"   Success Rate: {report['operations']['success_rate']}%",
        ]

        if report["issues"]:
            lines.append("   ⚠️ Issues detected:")
            for issue in report["issues"]:
                lines.append(f"      - {issue['message']}")
        else:
            lines.append("   ✅ All systems nominal")

        return "\n".join(lines)

    def is_healthy(self) -> bool:
        """Quick check if agent is healthy (not degraded or critical)."""
        report = self.check_health()
        return report["status"] in (HealthStatus.HEALTHY.value, HealthStatus.UNKNOWN.value)

    def get_statistics(self) -> dict:
        """Get aggregated statistics for external analysis."""
        report = self.check_health()
        return {
            "status": report["status"],
            "cpu_avg": report["metrics"]["cpu_percent"]["average_60s"],
            "memory_avg": report["metrics"]["memory_percent"]["average_60s"],
            "latency_avg": report["metrics"]["api_latency_ms"]["average"],
            "success_rate": report["operations"]["success_rate"],
            "issue_count": len(report["issues"]),
        }
