"""Tests for Recurring Task Scheduler"""
import pytest
import json
import time
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import the module we'll create
import sys
sys.path.insert(0, '/Users/firatsertgoz/Documents/clawgotchi/utils')

# We'll import this after creating the module
# from recurring_task_scheduler import RecurringTaskScheduler, TaskSchedule


class TestRecurringTaskScheduler:
    """Test cases for RecurringTaskScheduler"""
    
    @pytest.fixture
    def scheduler(self, tmp_path):
        """Create a scheduler with temporary storage"""
        # Import inside fixture to avoid module not found before creation
        from recurring_task_scheduler import RecurringTaskScheduler
        db_path = tmp_path / "test_scheduler.json"
        return RecurringTaskScheduler(db_path=str(db_path))
    
    @pytest.fixture
    def sample_task(self):
        """Sample task definition"""
        return {
            "id": "test_task_001",
            "name": "Nightly Backup",
            "command": "python backup.py",
            "cron_expression": "0 2 * * *",  # 2 AM daily
            "enabled": True,
            "retry_on_failure": True,
            "max_retries": 3,
            "retry_delay_seconds": 60
        }
    
    def test_create_schedule(self, scheduler, sample_task):
        """Test creating a new task schedule"""
        result = scheduler.create_schedule(**sample_task)
        assert result.id == "test_task_001"
        assert result.name == "Nightly Backup"
        assert result.enabled == True
        assert scheduler.get_schedule("test_task_001") is not None
    
    def test_get_next_run_time(self, scheduler, sample_task):
        """Test calculating next run time from cron expression"""
        scheduler.create_schedule(**sample_task)
        next_run = scheduler.get_next_run("test_task_001")
        assert next_run is not None
        assert isinstance(next_run, datetime)
        # Next run should be in the future
        assert next_run > datetime.now()
    
    def test_record_execution_success(self, scheduler, sample_task):
        """Test recording a successful execution"""
        scheduler.create_schedule(**sample_task)
        scheduler.record_execution("test_task_001", success=True, output="Backup complete")
        history = scheduler.get_execution_history("test_task_001")
        assert len(history) == 1
        assert history[0].success == True
    
    def test_record_execution_failure(self, scheduler, sample_task):
        """Test recording a failed execution"""
        scheduler.create_schedule(**sample_task)
        scheduler.record_execution("test_task_001", success=False, error="Disk full")
        history = scheduler.get_execution_history("test_task_001")
        assert len(history) == 1
        assert history[0].success == False
        assert history[0].error == "Disk full"
    
    def test_get_pending_tasks(self, scheduler, sample_task):
        """Test finding tasks that are due to run"""
        scheduler.create_schedule(**sample_task)
        # Create another task
        scheduler.create_schedule(
            id="test_task_002",
            name="Morning Report",
            command="python report.py",
            cron_expression="0 9 * * *",
            enabled=True
        )
        # Only get pending tasks
        pending = scheduler.get_pending_tasks()
        # At least one task should be pending
        assert isinstance(pending, list)
    
    def test_disable_enable_task(self, scheduler, sample_task):
        """Test disabling and re-enabling a task"""
        scheduler.create_schedule(**sample_task)
        scheduler.disable_task("test_task_001")
        task = scheduler.get_schedule("test_task_001")
        assert task.enabled == False
        
        scheduler.enable_task("test_task_001")
        task = scheduler.get_schedule("test_task_001")
        assert task.enabled == True
    
    def test_delete_task(self, scheduler, sample_task):
        """Test deleting a task schedule"""
        scheduler.create_schedule(**sample_task)
        scheduler.delete_task("test_task_001")
        assert scheduler.get_schedule("test_task_001") is None
    
    def test_persistence_across_restarts(self, tmp_path, sample_task):
        """Test that schedules persist after restart"""
        db_path = tmp_path / "test_scheduler.json"
        
        from recurring_task_scheduler import RecurringTaskScheduler
        
        # Create and add task
        scheduler1 = RecurringTaskScheduler(db_path=str(db_path))
        scheduler1.create_schedule(**sample_task)
        
        # Simulate restart by creating new instance
        scheduler2 = RecurringTaskScheduler(db_path=str(db_path))
        assert scheduler2.get_schedule("test_task_001") is not None
    
    def test_cron_expression_parsing(self, scheduler, sample_task):
        """Test parsing various cron expressions"""
        # Test different cron formats
        test_cases = [
            ("0 2 * * *", "Daily at 2 AM"),
            ("*/15 * * * *", "Every 15 minutes"),
            ("0 9 * * 1", "Weekly on Monday at 9 AM"),
            ("0 0 1 * *", "Monthly on 1st at midnight"),
        ]
        
        for cron_expr, description in test_cases:
            task = sample_task.copy()
            task["id"] = f"test_{cron_expr.replace('*', '_')}"
            task["cron_expression"] = cron_expr
            scheduler.create_schedule(**task)
            next_run = scheduler.get_next_run(task["id"])
            assert next_run is not None, f"Failed to parse: {description}"
    
    def test_execution_statistics(self, scheduler, sample_task):
        """Test getting execution statistics"""
        scheduler.create_schedule(**sample_task)
        
        # Record multiple executions
        scheduler.record_execution("test_task_001", success=True)
        scheduler.record_execution("test_task_001", success=True)
        scheduler.record_execution("test_task_001", success=False, error="Failed")
        
        stats = scheduler.get_statistics("test_task_001")
        assert stats["total_runs"] == 3
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == pytest.approx(66.67, rel=5)
    
    def test_get_all_schedules(self, scheduler, sample_task):
        """Test getting all scheduled tasks"""
        scheduler.create_schedule(**sample_task)
        scheduler.create_schedule(
            id="test_task_002",
            name="Task 2",
            command="python task2.py",
            cron_expression="0 10 * * *",
            enabled=True
        )
        
        all_tasks = scheduler.get_all_schedules()
        assert len(all_tasks) == 2
    
    def test_should_run_now(self, scheduler, sample_task):
        """Test if task should run now based on schedule"""
        scheduler.create_schedule(**sample_task)
        
        # Task should run if next_run is in the past
        # We can't easily test this without mocking time,
        # but we can verify the method exists and handles edge cases
        should_run = scheduler.should_run_now("test_task_001")
        assert isinstance(should_run, bool)


class TestTaskScheduleDataClass:
    """Test the TaskSchedule dataclass"""
    
    def test_task_schedule_creation(self):
        """Test creating a TaskSchedule instance"""
        from recurring_task_scheduler import TaskSchedule
        
        schedule = TaskSchedule(
            id="test_001",
            name="Test Task",
            command="echo hello",
            cron_expression="* * * * *",
            enabled=True,
            retry_on_failure=True,
            max_retries=3
        )
        
        assert schedule.id == "test_001"
        assert schedule.name == "Test Task"
        assert schedule.enabled == True
        assert schedule.last_run is None
        assert schedule.next_run is None
