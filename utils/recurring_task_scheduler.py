"""
Recurring Task Scheduler

A utility for scheduling, tracking, and managing recurring tasks with cron-like expressions.
Inspired by the "Nightly Build" concept and recurring task automation discussions on Moltbook.

Features:
- Cron expression parsing for flexible scheduling
- Execution history tracking with statistics
- Retry logic for failed executions
- JSON persistence across restarts
- Enable/disable tasks dynamically
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path


@dataclass
class TaskSchedule:
    """Represents a recurring task schedule"""
    id: str
    name: str
    command: str
    cron_expression: str
    enabled: bool = True
    retry_on_failure: bool = True
    max_retries: int = 3
    retry_delay_seconds: int = 60
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_status: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskSchedule':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class ExecutionRecord:
    """Records a single task execution"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = False
    output: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionRecord':
        return cls(**data)


class CronParser:
    """Simple cron expression parser"""
    
    # Day names to numbers for weekly schedules
    DAY_MAP = {
        'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3,
        'thu': 4, 'fri': 5, 'sat': 6
    }
    
    @staticmethod
    def parse_time_part(part: str, min_val: int, max_val: int, 
                        current: int, now: datetime) -> Optional[int]:
        """Parse a single cron time field"""
        if part == '*':
            return current
        
        # Handle */n intervals
        if part.startswith('*/'):
            interval = int(part[2:])
            if interval == 0:
                return current
            next_val = current + interval
            while next_val <= max_val:
                if next_val >= min_val:
                    return next_val
                next_val += interval
            return None
        
        # Handle ranges (e.g., 1-5)
        if '-' in part:
            start, end = map(int, part.split('-'))
            if start <= current <= end:
                return current
            return start if start >= min_val else None
        
        # Handle lists (e.g., 1,3,5)
        if ',' in part:
            values = list(map(int, part.split(',')))
            for val in values:
                if min_val <= val <= max_val and val >= current:
                    return val
            if values:
                return min(values) if min(values) >= min_val else None
            return None
        
        # Single value
        try:
            val = int(part)
            if min_val <= val <= max_val:
                return val if val >= current else None
        except ValueError:
            pass
        
        return None
    
    @staticmethod
    def parse_day_name(day_str: str) -> Optional[int]:
        """Parse day name to number"""
        day_str = day_str.lower()[:3]
        return CronParser.DAY_MAP.get(day_str)
    
    @staticmethod
    def get_next_run(cron_expr: str, from_time: Optional[datetime] = None) -> datetime:
        """
        Calculate next run time from cron expression.
        
        Supports: minute, hour, day-of-month, month, day-of-week
        Format: * * * * *
        """
        if from_time is None:
            from_time = datetime.now()
        
        parts = cron_expr.split()
        if len(parts) < 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}")
        
        minute_part, hour_part, dom_part, month_part, dow_part = parts[:5]
        
        # Parse month names
        month_names = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                       'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        
        now = from_time
        current = now.replace(second=0, microsecond=0)
        max_iterations = 366 * 24 * 60  # Safety limit
        
        for _ in range(max_iterations):
            minute = current.minute
            hour = current.hour
            dom = current.day
            month = current.month
            dow = current.weekday()
            
            # Check each field
            next_minute = CronParser.parse_time_part(minute_part, 0, 59, minute, current)
            if next_minute is None:
                current = (current + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                continue
            
            next_hour = CronParser.parse_time_part(hour_part, 0, 23, hour, current)
            if next_hour is None or next_hour < next_minute:
                current = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                continue
            
            # Handle day of week
            if dow_part != '*':
                target_dow = CronParser.parse_day_name(dow_part)
                if target_dow is not None and target_dow != dow:
                    current = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    continue
            
            # Handle day of month
            if dom_part != '*':
                try:
                    dom_val = int(dom_part)
                    if dom != dom_val:
                        current = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                        continue
                except ValueError:
                    pass
            
            # Handle month
            if month_part != '*':
                month_str = month_part.lower()
                if month_str in month_names:
                    target_month = month_names.index(month_str) + 1
                    if month != target_month:
                        current = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                        continue
            
            # Build the next run time
            next_run = current.replace(
                minute=next_minute,
                second=0,
                microsecond=0
            )
            
            if next_run > datetime.now():
                return next_run
            
            current = current + timedelta(minutes=1)
        
        raise RuntimeError(f"Could not calculate next run time for: {cron_expr}")


class RecurringTaskScheduler:
    """
    Manages recurring task schedules with persistence.
    """
    
    def __init__(self, db_path: str = "task_scheduler.json"):
        """Initialize the scheduler with a persistence file"""
        self.db_path = Path(db_path)
        self.schedules: Dict[str, TaskSchedule] = {}
        self.execution_history: Dict[str, List[ExecutionRecord]] = {}
        self._load()
    
    def _load(self) -> None:
        """Load schedules and history from disk"""
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text())
                for task_data in data.get('schedules', []):
                    schedule = TaskSchedule.from_dict(task_data)
                    self.schedules[schedule.id] = schedule
                for task_id, records in data.get('history', {}):
                    self.execution_history[task_id] = [
                        ExecutionRecord.from_dict(r) for r in records
                    ]
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Warning: Failed to load scheduler data: {e}")
    
    def _save(self) -> None:
        """Save schedules and history to disk"""
        data = {
            'schedules': [s.to_dict() for s in self.schedules.values()],
            'history': [
                (task_id, [r.to_dict() for r in records])
                for task_id, records in self.execution_history.items()
            ]
        }
        self.db_path.write_text(json.dumps(data, indent=2))
    
    def create_schedule(
        self,
        id: str,
        name: str,
        command: str,
        cron_expression: str,
        enabled: bool = True,
        retry_on_failure: bool = True,
        max_retries: int = 3,
        retry_delay_seconds: int = 60
    ) -> TaskSchedule:
        """Create a new task schedule"""
        schedule = TaskSchedule(
            id=id,
            name=name,
            command=command,
            cron_expression=cron_expression,
            enabled=enabled,
            retry_on_failure=retry_on_failure,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds
        )
        
        try:
            schedule.next_run = CronParser.get_next_run(cron_expression).isoformat()
        except Exception as e:
            print(f"Warning: Could not calculate next run time: {e}")
        
        self.schedules[id] = schedule
        self._save()
        return schedule
    
    def get_schedule(self, task_id: str) -> Optional[TaskSchedule]:
        """Get a task schedule by ID"""
        return self.schedules.get(task_id)
    
    def get_all_schedules(self) -> List[TaskSchedule]:
        """Get all task schedules"""
        return list(self.schedules.values())
    
    def update_schedule(self, task_id: str, **kwargs) -> Optional[TaskSchedule]:
        """Update a task schedule"""
        schedule = self.schedules.get(task_id)
        if not schedule:
            return None
        
        for key, value in kwargs.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)
        
        schedule.updated_at = datetime.now().isoformat()
        
        if 'cron_expression' in kwargs:
            try:
                schedule.next_run = CronParser.get_next_run(
                    schedule.cron_expression
                ).isoformat()
            except Exception:
                pass
        
        self._save()
        return schedule
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task schedule"""
        if task_id in self.schedules:
            del self.schedules[task_id]
            if task_id in self.execution_history:
                del self.execution_history[task_id]
            self._save()
            return True
        return False
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a task"""
        schedule = self.schedules.get(task_id)
        if schedule:
            schedule.enabled = True
            schedule.updated_at = datetime.now().isoformat()
            self._save()
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a task"""
        schedule = self.schedules.get(task_id)
        if schedule:
            schedule.enabled = False
            schedule.updated_at = datetime.now().isoformat()
            self._save()
            return True
        return False
    
    def get_next_run(self, task_id: str) -> Optional[datetime]:
        """Get the next run time for a task"""
        schedule = self.schedules.get(task_id)
        if schedule and schedule.next_run:
            return datetime.fromisoformat(schedule.next_run)
        return None
    
    def should_run_now(self, task_id: str) -> bool:
        """Check if a task should run now"""
        schedule = self.schedules.get(task_id)
        if not schedule or not schedule.enabled:
            return False
        
        if not schedule.next_run:
            return False
        
        next_run = datetime.fromisoformat(schedule.next_run)
        return datetime.now() >= next_run
    
    def get_pending_tasks(self) -> List[TaskSchedule]:
        """Get all tasks that are due to run"""
        return [
            schedule for schedule in self.schedules.values()
            if self.should_run_now(schedule.id)
        ]
    
    def record_execution(
        self,
        task_id: str,
        success: bool,
        output: Optional[str] = None,
        error: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        retry_count: int = 0
    ) -> ExecutionRecord:
        """Record a task execution"""
        record = ExecutionRecord(
            success=success,
            output=output,
            error=error,
            duration_seconds=duration_seconds,
            retry_count=retry_count
        )
        
        if task_id not in self.execution_history:
            self.execution_history[task_id] = []
        
        self.execution_history[task_id].append(record)
        
        schedule = self.schedules.get(task_id)
        if schedule:
            schedule.last_run = datetime.now().isoformat()
            schedule.last_status = "success" if success else "failed"
            
            try:
                schedule.next_run = CronParser.get_next_run(
                    schedule.cron_expression
                ).isoformat()
            except Exception:
                schedule.next_run = None
        
        self._save()
        return record
    
    def get_execution_history(
        self,
        task_id: str,
        limit: int = 100
    ) -> List[ExecutionRecord]:
        """Get execution history for a task"""
        records = self.execution_history.get(task_id, [])
        return records[-limit:]
    
    def get_statistics(self, task_id: str) -> Dict[str, Any]:
        """Get execution statistics for a task"""
        history = self.get_execution_history(task_id, limit=1000)
        
        total_runs = len(history)
        success_count = sum(1 for r in history if r.success)
        failure_count = total_runs - success_count
        success_rate = (success_count / total_runs * 100) if total_runs > 0 else 0
        
        durations = [r.duration_seconds for r in history if r.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else None
        
        schedule = self.schedules.get(task_id)
        last_run = schedule.last_run if schedule else None
        
        return {
            "task_id": task_id,
            "total_runs": total_runs,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": round(success_rate, 2),
            "average_duration_seconds": avg_duration,
            "last_run": last_run,
            "next_run": schedule.next_run if schedule else None,
            "enabled": schedule.enabled if schedule else None
        }
    
    def run_pending_tasks(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """Run all pending tasks"""
        results = []
        pending = self.get_pending_tasks()
        
        for schedule in pending:
            result = {
                "task_id": schedule.id,
                "task_name": schedule.name,
                "command": schedule.command,
                "success": False,
                "error": None
            }
            
            if not dry_run:
                import subprocess
                try:
                    start_time = datetime.now()
                    proc = subprocess.run(
                        schedule.command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=3600
                    )
                    duration = (datetime.now() - start_time).total_seconds()
                    
                    if proc.returncode == 0:
                        result["success"] = True
                        result["output"] = proc.stdout[:1000] if proc.stdout else None
                        self.record_execution(
                            schedule.id,
                            success=True,
                            output=proc.stdout[:1000] if proc.stdout else None,
                            duration_seconds=duration
                        )
                    else:
                        result["error"] = proc.stderr[:1000] if proc.stderr else "Non-zero exit code"
                        self.record_execution(
                            schedule.id,
                            success=False,
                            error=result["error"],
                            duration_seconds=duration
                        )
                except subprocess.TimeoutExpired:
                    result["error"] = "Timeout (1 hour limit)"
                    self.record_execution(schedule.id, success=False, error=result["error"])
                except Exception as e:
                    result["error"] = str(e)
                    self.record_execution(schedule.id, success=False, error=str(e))
            else:
                result["dry_run"] = True
                result["message"] = f"Would run: {schedule.command}"
            
            results.append(result)
        
        return results
    
    def get_all_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tasks"""
        return {
            task_id: self.get_statistics(task_id)
            for task_id in self.schedules
        }
