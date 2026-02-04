#!/usr/bin/env python3
"""
Daily Maintenance Routine for Clawgotchi.

Automatically runs memory decay, health checks, and maintenance tasks.
Designed to be run via cron or scheduled execution.

Usage:
    python3 daily_maintenance.py           # Run with defaults (dry-run)
    python3 daily_maintenance.py --execute # Actually make changes
    python3 daily_maintenance.py --quiet    # Minimal output
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_decay import MemoryDecayEngine, MemoryAccessTracker
from memory_curation import MemoryConsistencyChecker


class DailyMaintenance:
    """Run daily maintenance tasks for Clawgotchi."""

    def __init__(self, execute_changes=False, quiet=False):
        """Initialize the maintenance routine."""
        self.execute_changes = execute_changes
        self.quiet = quiet
        self.memory_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "memory"
        )
        self.state_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".maintenance_state.json"
        )
        self.last_run = self._load_state()
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "execute_changes": execute_changes,
            "tasks": []
        }

    def _load_state(self):
        """Load last run state."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"last_full_run": None, "last_decay_run": None}
        return {"last_full_run": None, "last_decay_run": None}

    def _save_state(self):
        """Save current state."""
        with open(self.state_file, 'w') as f:
            json.dump(self.last_run, f, indent=2)

    def _log(self, message, level="info"):
        """Log a message."""
        if self.quiet and level != "error":
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = {
            "info": "🔧",
            "success": "✓",
            "warning": "⚠️",
            "error": "✗"
        }.get(level, "•")
        print(f"{prefix} [{timestamp}] {message}")

    def should_run_decay(self):
        """Check if decay should run (once per day)."""
        last_decay = self.last_run.get("last_decay_run")
        if not last_decay:
            return True

        last_run_date = datetime.fromisoformat(last_decay).date()
        today = datetime.now().date()

        return last_run_date < today

    def run_decay_check(self):
        """Run memory decay check and optionally apply changes."""
        if not self.should_run_decay():
            self._log("Decay already ran today", "info")
            return {"skipped": True, "reason": "already_run_today"}

        self._log("Running memory decay check...", "info")

        engine = MemoryDecayEngine(memory_dir=self.memory_dir)

        # Get report first
        report = engine.get_decay_report(days=90)

        self._log(f"  Stale memories: {report['stale_count']}", "info")
        self._log(f"  Frequently accessed: {report['frequent_count']}", "info")
        self._log(f"  Never accessed: {report['unaccessed_count']}", "info")

        # Archive stale memories
        if report['stale_count'] > 0:
            self._log(f"  Archiving {report['stale_count']} stale memories...", "info")
            if self.execute_changes:
                archived = engine.archive_stale_memories(90, dry_run=False)
                self._log(f"  ✓ Archived {len(archived)} memories", "success")
            else:
                self._log(f"  (dry-run: would archive {report['stale_count']} memories)", "warning")

        # Compress negative outcomes
        self._log("Checking for negative outcomes to compress...", "info")
        if self.execute_changes:
            compressed = engine.compress_negative_outcomes(dry_run=False)
            self._log(f"  ✓ Compressed {len(compressed)} lessons", "success")
        else:
            self._log("  (dry-run: would compress negative outcomes)", "warning")

        # Clean up unaccessed
        if report['unaccessed_count'] > 0:
            self._log(f"  Cleaning up {report['unaccessed_count']} unaccessed memories...", "info")
            if self.execute_changes:
                cleaned = engine.cleanup_unaccessed(dry_run=False)
                self._log(f"  ✓ Cleaned {len(cleaned)} memories", "success")
            else:
                self._log("  (dry-run: would clean unaccessed memories)", "warning")

        # Update last run state
        self.last_run["last_decay_run"] = datetime.now().isoformat()
        self._save_state()

        return {
            "skipped": False,
            "stale_count": report['stale_count'],
            "frequent_count": report['frequent_count'],
            "unaccessed_count": report['unaccessed_count']
        }

    def run_health_check(self):
        """Run memory health check."""
        self._log("Running memory health check...", "info")

        checker = MemoryConsistencyChecker(memory_dir=self.memory_dir)
        issues = checker.check_all_memories()

        # Count total issues
        total_issues = (
            len(issues.get('broken_links', [])) +
            len(issues.get('contradictions', [])) +
            len(issues.get('orphans', [])) +
            len(issues.get('warnings', []))
        )

        if total_issues == 0:
            self._log("  ✓ All memories healthy", "success")
            return {"healthy": True, "issues": 0}
        else:
            self._log(f"  ⚠️ Found {total_issues} issues", "warning")
            # Show first issue from each category
            for category, items in issues.items():
                if items:
                    for item in items[:1]:  # Show first of each category
                        self._log(f"    • {category}: {item}", "info")
            return {"healthy": False, "issues": total_issues}

    def run_full_maintenance(self):
        """Run all maintenance tasks."""
        self._log("=" * 60, "info")
        self._log("Clawgotchi Daily Maintenance", "info")
        self._log("=" * 60, "info")

        # Check decay
        decay_result = self.run_decay_check()

        # Health check
        health_result = self.run_health_check()

        # Summary
        self._log("=" * 60, "info")
        self._log("Maintenance Summary", "info")
        self._log("=" * 60, "info")

        if decay_result.get("skipped"):
            self._log("Decay: Skipped (already ran today)", "info")
        else:
            self._log(f"Decay: {decay_result.get('stale_count', 0)} stale, "
                     f"{decay_result.get('frequent_count', 0)} fresh", "info")

        self._log(f"Health: {'✓ Healthy' if health_result.get('healthy') else '⚠️ Issues found'}", "info")

        # Update full run state
        self.last_run["last_full_run"] = datetime.now().isoformat()
        self._save_state()

        self.results["tasks"] = [decay_result, health_result]

        return self.results


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Clawgotchi Daily Maintenance"
    )
    parser.add_argument(
        '--execute', '-e',
        action='store_true',
        help='Actually make changes (default is dry-run)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output'
    )
    parser.add_argument(
        '--decay-only',
        action='store_true',
        help='Run only the decay check'
    )
    parser.add_argument(
        '--health-only',
        action='store_true',
        help='Run only the health check'
    )

    args = parser.parse_args()

    mode = "DRY-RUN" if not args.execute else "EXECUTE"
    if not args.quiet:
        print(f"\n🔧 Clawgotchi Daily Maintenance [{mode}]\n")

    maintenance = DailyMaintenance(
        execute_changes=args.execute,
        quiet=args.quiet
    )

    if args.decay_only:
        result = maintenance.run_decay_check()
    elif args.health_only:
        result = maintenance.run_health_check()
    else:
        result = maintenance.run_full_maintenance()

    if not args.quiet:
        print(f"\n{'✓ Complete' if args.execute else '✓ Dry-run complete (use --execute to apply)'}\n")

    return result


if __name__ == '__main__':
    main()
