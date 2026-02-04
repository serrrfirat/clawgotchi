"""
Tests for TaskAuditLog - Track claimed vs actual task completion
"""

import json
import os
import tempfile
import pytest
from task_audit import (
    TaskAuditLog,
    TaskStatus,
    TaskRecord,
    create_audit_log,
    claim_task,
    complete_task,
    verify_task
)


@pytest.fixture
def temp_log():
    """Create a temporary log file for each test"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def audit(temp_log):
    """Create a TaskAuditLog instance with temp file"""
    return TaskAuditLog(temp_log)


class TestTaskRecord:
    """Tests for TaskRecord class"""
    
    def test_create_record(self):
        """Test basic record creation"""
        record = TaskRecord(
            task_id="abc123",
            description="Test task",
            claimed_at=1234567890.0,
            status=TaskStatus.CLAIMED
        )
        assert record.task_id == "abc123"
        assert record.description == "Test task"
        assert record.status == TaskStatus.CLAIMED
        assert record.evidence == {}
        assert record.metadata == {}
    
    def test_record_with_metadata(self):
        """Test record with metadata"""
        record = TaskRecord(
            task_id="abc123",
            description="Test task",
            claimed_at=1234567890.0,
            metadata={"priority": "high", "project": "test"}
        )
        assert record.metadata["priority"] == "high"
        assert record.metadata["project"] == "test"
    
    def test_record_to_dict(self):
        """Test record serialization"""
        record = TaskRecord(
            task_id="abc123",
            description="Test task",
            claimed_at=1234567890.0,
            status=TaskStatus.COMPLETED,
            completed_at=1234567895.0,
            evidence={"tests_passed": 10},
            metadata={"priority": "high"}
        )
        data = record.to_dict()
        assert data["task_id"] == "abc123"
        assert data["status"] == "completed"
        assert data["evidence"]["tests_passed"] == 10
    
    def test_record_from_dict(self):
        """Test record deserialization"""
        data = {
            "task_id": "abc123",
            "description": "Test task",
            "claimed_at": 1234567890.0,
            "status": "completed",
            "completed_at": 1234567895.0,
            "evidence": {"tests_passed": 10},
            "metadata": {"priority": "high"}
        }
        record = TaskRecord.from_dict(data)
        assert record.task_id == "abc123"
        assert record.status == TaskStatus.COMPLETED
        assert record.evidence["tests_passed"] == 10


class TestTaskAuditLog:
    """Tests for TaskAuditLog class"""
    
    def test_claim_task(self, audit):
        """Test claiming a task"""
        task_id = audit.claim("Build feature X")
        assert task_id is not None
        assert len(task_id) == 8  # UUID short form
        
        record = audit.get_record(task_id)
        assert record is not None
        assert record["description"] == "Build feature X"
        assert record["status"] == "claimed"
    
    def test_claim_with_metadata(self, audit):
        """Test claiming with metadata"""
        task_id = audit.claim(
            "Build feature X",
            metadata={"priority": "high", "component": "auth"}
        )
        record = audit.get_record(task_id)
        assert record["metadata"]["priority"] == "high"
        assert record["metadata"]["component"] == "auth"
    
    def test_start_task(self, audit):
        """Test marking task as in progress"""
        task_id = audit.claim("Build feature X")
        result = audit.start(task_id)
        assert result is True
        record = audit.get_record(task_id)
        assert record["status"] == "in_progress"
    
    def test_start_nonexistent_task(self, audit):
        """Test starting a task that doesn't exist"""
        result = audit.start("nonexistent")
        assert result is False
    
    def test_complete_task(self, audit):
        """Test completing a task"""
        task_id = audit.claim("Build feature X")
        result = audit.complete(task_id, evidence={"tests_passed": 17, "commit": "abc123"})
        assert result is True
        record = audit.get_record(task_id)
        assert record["status"] == "completed"
        assert record["evidence"]["tests_passed"] == 17
        assert record["completed_at"] is not None
    
    def test_complete_nonexistent_task(self, audit):
        """Test completing a task that doesn't exist"""
        result = audit.complete("nonexistent")
        assert result is False
    
    def test_fail_task(self, audit):
        """Test marking a task as failed"""
        task_id = audit.claim("Build feature X")
        result = audit.fail(task_id, "Resource not available")
        assert result is True
        record = audit.get_record(task_id)
        assert record["status"] == "failed"
        assert record["evidence"]["failure_reason"] == "Resource not available"
    
    def test_verify_task(self, audit):
        """Test verifying a task"""
        task_id = audit.claim("Build feature X")
        audit.complete(task_id)
        result = audit.verify(task_id, verifier="human", notes="All tests pass")
        assert result is True
        record = audit.get_record(task_id)
        assert record["status"] == "verified"
        assert record["evidence"]["verified_by"] == "human"
        assert record["evidence"]["verification_notes"] == "All tests pass"
    
    def test_verify_nonexistent_task(self, audit):
        """Test verifying a task that doesn't exist"""
        result = audit.verify("nonexistent")
        assert result is False
    
    def test_get_unverified(self, audit):
        """Test getting unverified tasks"""
        id1 = audit.claim("Task 1")
        id2 = audit.claim("Task 2")
        id3 = audit.claim("Task 3")
        
        audit.complete(id1)
        audit.complete(id2)
        audit.verify(id1)  # Only verify task 1
        
        unverified = audit.get_unverified()
        assert len(unverified) == 2
        unverified_ids = [r["task_id"] for r in unverified]
        assert id3 in unverified_ids
        assert id2 in unverified_ids
        assert id1 not in unverified_ids
    
    def test_get_verified(self, audit):
        """Test getting verified tasks"""
        id1 = audit.claim("Task 1")
        id2 = audit.claim("Task 2")
        
        audit.complete(id1)
        audit.complete(id2)
        audit.verify(id1)
        
        verified = audit.get_verified()
        assert len(verified) == 1
        assert verified[0]["task_id"] == id1
    
    def test_report(self, audit):
        """Test generating audit report"""
        id1 = audit.claim("Task 1")
        id2 = audit.claim("Task 2")
        id3 = audit.claim("Task 3")
        
        audit.start(id1)
        audit.complete(id1, evidence={"tests": 10})
        audit.complete(id2, evidence={"tests": 5})
        audit.fail(id3, "Blocked")
        audit.verify(id1, verifier="test_suite")
        
        report = audit.report()
        
        assert report["total_tasks"] == 3
        assert report["claimed"] == 0
        assert report["in_progress"] == 0
        assert report["completed"] == 2
        assert report["failed"] == 1
        assert report["verified"] == 1
        # 2 completed, 1 failed = 3 completable
        assert report["completion_rate_percent"] == pytest.approx(66.67, abs=0.1)
        # 1 verified, 2 completed = 50%
        assert report["verification_rate_percent"] == 50.0
        assert "unverified_tasks" in report
        assert "generated_at" in report
    
    def test_persistence(self, temp_log):
        """Test that records persist to disk"""
        # Create and modify
        audit1 = TaskAuditLog(temp_log)
        task_id = audit1.claim("Persistent task")
        audit1.complete(task_id)
        
        # Create new instance (simulating restart)
        audit2 = TaskAuditLog(temp_log)
        record = audit2.get_record(task_id)
        
        assert record is not None
        assert record["status"] == "completed"
        assert record["description"] == "Persistent task"
    
    def test_clear(self, audit):
        """Test clearing all records"""
        audit.claim("Task 1")
        audit.claim("Task 2")
        audit.claim("Task 3")
        
        count = audit.clear()
        assert count == 3
        
        report = audit.report()
        assert report["total_tasks"] == 0
    
    def test_workflow_complete(self, audit):
        """Test complete workflow: claim -> start -> complete -> verify"""
        # Claim
        task_id = audit.claim(
            "Build user authentication",
            metadata={"priority": "high", "sprint": "Sprint 7"}
        )
        
        # Start
        audit.start(task_id)
        record = audit.get_record(task_id)
        assert record["status"] == "in_progress"
        
        # Complete with evidence
        audit.complete(
            task_id,
            evidence={
                "tests_passed": 42,
                "commit_sha": "abc123def456",
                "files_changed": 12
            }
        )
        record = audit.get_record(task_id)
        assert record["status"] == "completed"
        assert record["evidence"]["tests_passed"] == 42
        
        # Verify
        audit.verify(
            task_id,
            verifier="CI_pipeline",
            notes="All tests passing, code reviewed"
        )
        record = audit.get_record(task_id)
        assert record["status"] == "verified"
        assert record["evidence"]["verified_by"] == "CI_pipeline"
        
        # Report
        report = audit.report()
        assert report["verification_rate_percent"] == 100.0


class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    def test_create_audit_log(self, temp_log):
        """Test create_audit_log convenience function"""
        audit = create_audit_log(temp_log)
        task_id = audit.claim("Test task")
        assert task_id is not None
    
    def test_claim_task(self, audit):
        """Test claim_task convenience function"""
        task_id = claim_task(audit, "Test task", {"key": "value"})
        record = audit.get_record(task_id)
        assert record["description"] == "Test task"
        assert record["metadata"]["key"] == "value"
    
    def test_complete_task(self, audit):
        """Test complete_task convenience function"""
        task_id = audit.claim("Test task")
        result = complete_task(audit, task_id, {"result": "success"})
        assert result is True
        record = audit.get_record(task_id)
        assert record["status"] == "completed"
    
    def test_verify_task(self, audit):
        """Test verify_task convenience function"""
        task_id = audit.claim("Test task")
        audit.complete(task_id)
        result = verify_task(audit, task_id, "tester", "looks good")
        assert result is True
        record = audit.get_record(task_id)
        assert record["status"] == "verified"


class TestTaskStatus:
    """Tests for TaskStatus enum"""
    
    def test_status_values(self):
        """Test status enum values"""
        assert TaskStatus.CLAIMED.value == "claimed"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.VERIFIED.value == "verified"
    
    def test_status_from_value(self):
        """Test creating status from value"""
        status = TaskStatus("completed")
        assert status == TaskStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
