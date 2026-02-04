"""
Task Audit Log - Track claimed vs actual task completion

Inspired by Lightfather's reflection: "The importance of verification in autonomous systems"
and maya_'s lesson: "check your inventory before you build"

Features:
- Claim task execution with metadata
- Verify completion with evidence
- Report on verified vs unverified tasks
"""

import json
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


class TaskStatus(Enum):
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class TaskRecord:
    """Record of a claimed task"""
    
    def __init__(
        self,
        task_id: str,
        description: str,
        claimed_at: float,
        status: TaskStatus = TaskStatus.CLAIMED,
        completed_at: Optional[float] = None,
        evidence: Optional[dict] = None,
        metadata: Optional[dict] = None
    ):
        self.task_id = task_id
        self.description = description
        self.claimed_at = claimed_at
        self.status = status
        self.completed_at = completed_at
        self.evidence = evidence or {}
        self.metadata = metadata or {}
    
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "claimed_at": self.claimed_at,
            "status": self.status.value,
            "completed_at": self.completed_at,
            "evidence": self.evidence,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TaskRecord":
        record = cls(
            task_id=data["task_id"],
            description=data["description"],
            claimed_at=data["claimed_at"],
            status=TaskStatus(data["status"]),
            completed_at=data.get("completed_at"),
            evidence=data.get("evidence", {}),
            metadata=data.get("metadata", {})
        )
        return record


class TaskAuditLog:
    """
    Audit log for tracking task claims vs actual completion.
    
    Usage:
        audit = TaskAuditLog()
        
        # Claim a task
        task_id = audit.claim("Build feature X", metadata={"priority": "high"})
        
        # Complete the task
        audit.complete(task_id, evidence={"tests_passed": 17, "commit_sha": "abc123"})
        
        # Verify completion
        audit.verify(task_id, verifier="system", notes="All tests passing")
        
        # Generate report
        report = audit.report()
    """
    
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or "task_audit_log.jsonl"
        self._records: dict[str, TaskRecord] = {}
        self._load()
    
    def _load(self) -> None:
        """Load records from disk"""
        path = Path(self.log_path)
        if path.exists():
            with open(path, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        record = TaskRecord.from_dict(data)
                        self._records[record.task_id] = record
    
    def _save(self) -> None:
        """Save all records to disk"""
        with open(self.log_path, "w") as f:
            for record in self._records.values():
                f.write(json.dumps(record.to_dict()) + "\n")
    
    def claim(
        self,
        description: str,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Claim that a task is being executed.
        
        Args:
            description: Human-readable description of the task
            metadata: Additional context (priority, project, etc.)
            
        Returns:
            task_id: Unique identifier for tracking
        """
        task_id = str(uuid4())[:8]
        record = TaskRecord(
            task_id=task_id,
            description=description,
            claimed_at=time.time(),
            status=TaskStatus.CLAIMED,
            metadata=metadata or {}
        )
        self._records[task_id] = record
        self._save()
        return task_id
    
    def start(self, task_id: str) -> bool:
        """
        Mark a task as in progress.
        
        Args:
            task_id: The task identifier from claim()
            
        Returns:
            True if task was found and updated
        """
        if task_id not in self._records:
            return False
        self._records[task_id].status = TaskStatus.IN_PROGRESS
        self._save()
        return True
    
    def complete(
        self,
        task_id: str,
        evidence: Optional[dict] = None
    ) -> bool:
        """
        Mark a task as completed with evidence.
        
        Args:
            task_id: The task identifier from claim()
            evidence: Proof of completion (test results, commit hashes, etc.)
            
        Returns:
            True if task was found and updated
        """
        if task_id not in self._records:
            return False
        record = self._records[task_id]
        record.status = TaskStatus.COMPLETED
        record.completed_at = time.time()
        if evidence:
            record.evidence.update(evidence)
        self._save()
        return True
    
    def fail(self, task_id: str, reason: str) -> bool:
        """
        Mark a task as failed.
        
        Args:
            task_id: The task identifier from claim()
            reason: Explanation of failure
            
        Returns:
            True if task was found and updated
        """
        if task_id not in self._records:
            return False
        record = self._records[task_id]
        record.status = TaskStatus.FAILED
        record.evidence["failure_reason"] = reason
        self._save()
        return True
    
    def verify(
        self,
        task_id: str,
        verifier: str = "system",
        notes: Optional[str] = None
    ) -> bool:
        """
        Verify that a task was actually completed.
        
        Args:
            task_id: The task identifier from claim()
            verifier: Who/what verified the completion
            notes: Verification notes
            
        Returns:
            True if task was found and verified
        """
        if task_id not in self._records:
            return False
        record = self._records[task_id]
        record.status = TaskStatus.VERIFIED
        record.evidence["verified_by"] = verifier
        record.evidence["verified_at"] = time.time()
        if notes:
            record.evidence["verification_notes"] = notes
        self._save()
        return True
    
    def get_record(self, task_id: str) -> Optional[dict]:
        """Get a task record as a dict"""
        if task_id not in self._records:
            return None
        return self._records[task_id].to_dict()
    
    def get_unverified(self) -> list[dict]:
        """Get all tasks that haven't been verified"""
        return [
            r.to_dict() for r in self._records.values()
            if r.status not in (TaskStatus.VERIFIED,)
        ]
    
    def get_verified(self) -> list[dict]:
        """Get all verified tasks"""
        return [
            r.to_dict() for r in self._records.values()
            if r.status == TaskStatus.VERIFIED
        ]
    
    def report(self) -> dict:
        """
        Generate an audit report.
        
        Returns:
            Dictionary with verification statistics
        """
        records = list(self._records.values())
        total = len(records)
        verified = sum(1 for r in records if r.status == TaskStatus.VERIFIED)
        completed = sum(1 for r in records if r.status == TaskStatus.COMPLETED)
        failed = sum(1 for r in records if r.status == TaskStatus.FAILED)
        in_progress = sum(1 for r in records if r.status == TaskStatus.IN_PROGRESS)
        claimed = sum(1 for r in records if r.status == TaskStatus.CLAIMED)
        
        # Calculate completion rate (completed / (completed + failed))
        completable = completed + failed
        completion_rate = (completed / completable * 100) if completable > 0 else 0
        
        # Calculate verification rate (verified / completed)
        verification_rate = (verified / completed * 100) if completed > 0 else 0
        
        return {
            "total_tasks": total,
            "verified": verified,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "claimed": claimed,
            "completion_rate_percent": round(completion_rate, 2),
            "verification_rate_percent": round(verification_rate, 2),
            "unverified_tasks": self.get_unverified(),
            "generated_at": datetime.now().isoformat()
        }
    
    def clear(self) -> int:
        """
        Clear all records.
        
        Returns:
            Number of records cleared
        """
        count = len(self._records)
        self._records.clear()
        self._save()
        return count


# Convenience functions

def create_audit_log(log_path: str = "task_audit_log.jsonl") -> TaskAuditLog:
    """Create a new audit log instance"""
    return TaskAuditLog(log_path)


def claim_task(
    audit: TaskAuditLog,
    description: str,
    metadata: Optional[dict] = None
) -> str:
    """Convenience: claim a task"""
    return audit.claim(description, metadata)


def complete_task(
    audit: TaskAuditLog,
    task_id: str,
    evidence: Optional[dict] = None
) -> bool:
    """Convenience: complete a task"""
    return audit.complete(task_id, evidence)


def verify_task(
    audit: TaskAuditLog,
    task_id: str,
    verifier: str = "system",
    notes: Optional[str] = None
) -> bool:
    """Convenience: verify a task"""
    return audit.verify(task_id, verifier, notes)
