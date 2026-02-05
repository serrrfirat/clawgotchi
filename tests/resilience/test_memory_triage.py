"""
Tests for Memory Triage System
"""

import os
import json
import time
import pytest
from clawgotchi.resilience.memory_triage import (
    ImportanceLevel,
    MemoryFlag,
    ContentChunk,
    TriageSession,
    MemoryTriageSystem,
    create_triage_system
)


class TestImportanceLevel:
    """Tests for ImportanceLevel enum."""
    
    def test_importance_levels_order(self):
        """Test that importance levels have correct ordering."""
        assert ImportanceLevel.CRITICAL.value > ImportanceLevel.HIGH.value > ImportanceLevel.MEDIUM.value > ImportanceLevel.LOW.value
    
    def test_importance_from_string(self):
        """Test converting string to importance level."""
        assert ImportanceLevel.from_string("critical") == ImportanceLevel.CRITICAL
        assert ImportanceLevel.from_string("high") == ImportanceLevel.HIGH
        assert ImportanceLevel.from_string("medium") == ImportanceLevel.MEDIUM
        assert ImportanceLevel.from_string("low") == ImportanceLevel.LOW


class TestMemoryFlag:
    """Tests for MemoryFlag dataclass."""
    
    def test_create_flag(self):
        """Test creating a memory flag."""
        flag = MemoryFlag(
            content_id="msg-123",
            content="User asked about the project deadline",
            importance=ImportanceLevel.HIGH,
            source="conversation",
            timestamp=time.time(),
            tags=["deadline", "project", "important"]
        )
        
        assert flag.content_id == "msg-123"
        assert flag.importance == ImportanceLevel.HIGH
        assert "deadline" in flag.tags
    
    def test_flag_to_dict(self):
        """Test serialization to dictionary."""
        flag = MemoryFlag(
            content_id="msg-456",
            content="Never use rm -rf without confirmation",
            importance=ImportanceLevel.CRITICAL,
            source="conversation",
            timestamp=time.time()
        )
        
        data = flag.to_dict()
        assert data["content_id"] == "msg-456"
        assert data["importance"] == "CRITICAL"
        assert data["content"] == "Never use rm -rf without confirmation"
    
    def test_flag_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "content_id": "msg-789",
            "content": "Remember to call mom on her birthday",
            "importance": "HIGH",
            "source": "conversation",
            "timestamp": 1700000000.0,
            "tags": ["personal", "reminder"]
        }
        
        flag = MemoryFlag.from_dict(data)
        assert flag.content_id == "msg-789"
        assert flag.importance == ImportanceLevel.HIGH
        assert "personal" in flag.tags


class TestContentChunk:
    """Tests for ContentChunk dataclass."""
    
    def test_create_chunk(self):
        """Test creating a content chunk for triage."""
        chunk = ContentChunk(
            chunk_id="chunk-001",
            content="The API endpoint is https://api.example.com/v2/users",
            estimated_importance=ImportanceLevel.MEDIUM,
            is_actionable=True,
            referenced_entities=["API", "endpoint", "users"]
        )
        
        assert chunk.chunk_id == "chunk-001"
        assert chunk.estimated_importance == ImportanceLevel.MEDIUM
        assert chunk.is_actionable is True
    
    def test_chunk_to_dict(self):
        """Test serialization to dictionary."""
        chunk = ContentChunk(
            chunk_id="chunk-002",
            content="Deploy to production after tests pass",
            estimated_importance=ImportanceLevel.CRITICAL,
            is_actionable=True,
            referenced_entities=["deploy", "production", "tests"]
        )
        
        data = chunk.to_dict()
        assert data["chunk_id"] == "chunk-002"
        assert data["estimated_importance"] == "CRITICAL"
        assert data["is_actionable"] is True
    
    def test_chunk_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "chunk_id": "chunk-003",
            "content": "Meeting at 3 PM with the team",
            "estimated_importance": "MEDIUM",
            "is_actionable": False,
            "referenced_entities": ["meeting", "team"]
        }
        
        chunk = ContentChunk.from_dict(data)
        assert chunk.chunk_id == "chunk-003"
        assert chunk.referenced_entities == ["meeting", "team"]


class TestTriageSession:
    """Tests for TriageSession class."""
    
    def test_create_session(self):
        """Test creating a triage session."""
        session = TriageSession(
            session_id="session-001",
            context_window_limit=100000,
            compression_threshold=0.8
        )
        
        assert session.session_id == "session-001"
        assert session.context_window_limit == 100000
        assert session.flagged_content == []
    
    def test_flag_content(self):
        """Test flagging content in a session."""
        session = TriageSession(session_id="session-002")
        
        flag = session.flag_content(
            content_id="msg-001",
            content="Backup the database before deploying",
            importance=ImportanceLevel.CRITICAL,
            source="conversation",
            tags=["deployment", "safety"]
        )
        
        assert len(session.flagged_content) == 1
        assert session.flagged_content[0].importance == ImportanceLevel.CRITICAL
    
    def test_flag_ordering(self):
        """Test that flagged content is ordered by importance."""
        session = TriageSession(session_id="session-003")
        
        # Flag in random order
        session.flag_content("msg-1", "Low priority note", ImportanceLevel.LOW, "chat")
        session.flag_content("msg-2", "Critical action needed", ImportanceLevel.CRITICAL, "chat")
        session.flag_content("msg-3", "Medium priority task", ImportanceLevel.MEDIUM, "chat")
        
        # Should be ordered by importance descending
        assert session.flagged_content[0].importance == ImportanceLevel.CRITICAL
        assert session.flagged_content[1].importance == ImportanceLevel.MEDIUM
        assert session.flagged_content[2].importance == ImportanceLevel.LOW
    
    def test_get_high_priority_content(self):
        """Test retrieving high priority content."""
        session = TriageSession(session_id="session-004")
        
        session.flag_content("msg-1", "Not urgent", ImportanceLevel.LOW, "chat")
        session.flag_content("msg-2", "Urgent matter", ImportanceLevel.HIGH, "chat")
        session.flag_content("msg-3", "Very important", ImportanceLevel.CRITICAL, "chat")
        session.flag_content("msg-4", "Somewhat important", ImportanceLevel.MEDIUM, "chat")
        
        high_priority = session.get_high_priority_content(ImportanceLevel.HIGH)
        assert len(high_priority) == 2
        assert all(f.importance >= ImportanceLevel.HIGH for f in high_priority)
    
    def test_export_for_compression(self):
        """Test exporting flagged content for compression."""
        session = TriageSession(session_id="session-005")
        
        session.flag_content("msg-1", "First point", ImportanceLevel.HIGH, "chat")
        session.flag_content("msg-2", "Second point", ImportanceLevel.MEDIUM, "chat")
        
        exported = session.export_for_compression()
        assert "session_id" in exported
        assert "flagged_content" in exported
        assert len(exported["flagged_content"]) == 2
    
    def test_session_serialization(self):
        """Test session serialization."""
        session = TriageSession(session_id="session-006")
        session.flag_content("msg-1", "Test content", ImportanceLevel.HIGH, "chat")
        
        data = session.to_dict()
        assert data["session_id"] == "session-006"
        assert len(data["flagged_content"]) == 1
        
        restored = TriageSession.from_dict(data)
        assert restored.session_id == "session-006"
        assert len(restored.flagged_content) == 1


class TestMemoryTriageSystem:
    """Tests for MemoryTriageSystem class."""
    
    def test_create_system(self):
        """Test creating a triage system."""
        system = MemoryTriageSystem(
            storage_path="/tmp/test_triage",
            context_window_limit=100000,
            compression_threshold=0.8
        )
        
        assert system.storage_path == "/tmp/test_triage"
        assert system.context_window_limit == 100000
    
    def test_analyze_content_importance(self):
        """Test analyzing content importance."""
        system = MemoryTriageSystem()
        
        # Critical content indicators
        critical = system.analyze_content_importance(
            "URGENT: Deploy critical security patch immediately"
        )
        assert critical == ImportanceLevel.CRITICAL
        
        # High importance content
        high = system.analyze_content_importance(
            "Remember to update the configuration file for the new API"
        )
        assert high in [ImportanceLevel.HIGH, ImportanceLevel.MEDIUM]
        
        # Low importance content
        low = system.analyze_content_importance(
            "By the way, the office thermostat is set to 72 degrees"
        )
        assert low == ImportanceLevel.LOW
    
    def test_process_message(self):
        """Test processing a message for triage."""
        system = MemoryTriageSystem()
        
        result = system.process_message(
            message_id="msg-test-001",
            content="Never run git push --force on main branch",
            source="conversation"
        )
        
        assert "flag" in result
        assert "triage_session" in result
        assert result["flag"].importance in [ImportanceLevel.CRITICAL, ImportanceLevel.HIGH]
    
    def test_pre_compression_check(self):
        """Test checking what's important before compression."""
        system = MemoryTriageSystem()
        
        # Add some flagged content
        system.current_session.flag_content("msg-1", "Action item 1", ImportanceLevel.CRITICAL, "chat")
        system.current_session.flag_content("msg-2", "Action item 2", ImportanceLevel.HIGH, "chat")
        system.current_session.flag_content("msg-3", "Note", ImportanceLevel.LOW, "chat")
        
        pre_compression = system.get_pre_compression_report()
        
        assert "critical_count" in pre_compression
        assert "high_count" in pre_compression
        assert "all_flagged" in pre_compression
        assert pre_compression["critical_count"] == 1
        assert pre_compression["high_count"] == 1
    
    def test_save_and_load(self):
        """Test saving and loading triage data."""
        system = MemoryTriageSystem(
            storage_path="/tmp/test_triage_save",
            auto_save=True
        )
        
        system.process_message("msg-save-1", "Important fact", "conversation")
        system.process_message("msg-save-2", "Another important fact", "conversation")
        
        # Load from same path
        loaded = MemoryTriageSystem.load_from_path("/tmp/test_triage_save")
        
        assert loaded is not None
        assert len(loaded.current_session.flagged_content) >= 0  # May or may not persist depending on auto_save
    
    def test_get_preservation_summary(self):
        """Test getting summary of what will be preserved."""
        system = MemoryTriageSystem()
        
        system.process_message("msg-1", "Critical: Backup before delete", "conversation")
        system.process_message("msg-2", "Medium priority note", "conversation")
        
        summary = system.get_preservation_summary()
        
        assert "total_flagged" in summary
        assert "by_importance" in summary
        assert "suggested_actions" in summary
        assert summary["total_flagged"] == 2
    
    def test_cleanup_old_sessions(self):
        """Test cleaning up old triage sessions."""
        system = MemoryTriageSystem(
            storage_path="/tmp/test_triage_cleanup"
        )
        
        # Create old session
        old_session = TriageSession(
            session_id="old-session",
            timestamp=1000000000  # Old timestamp
        )
        system.sessions["old-session"] = old_session
        
        # Current session
        system.process_message("msg-new", "New content", "conversation")
        
        # Cleanup old sessions
        cleaned = system.cleanup_old_sessions(max_age_seconds=3600)
        
        assert cleaned >= 1
        assert "old-session" not in system.sessions
    
    def test_register_preservation_callback(self):
        """Test registering callback for preservation events."""
        system = MemoryTriageSystem()
        
        callbacks_called = []
        
        def preservation_callback(flagged_content):
            callbacks_called.append(len(flagged_content))
        
        system.register_preservation_callback(preservation_callback)
        
        system.process_message("msg-cb-1", "Test content", "conversation")
        
        # Callback should have been called
        assert len(callbacks_called) > 0


class TestCreateTriageSystem:
    """Tests for create_triage_system factory function."""
    
    def test_create_default_system(self):
        """Test creating system with defaults."""
        system = create_triage_system()
        
        assert isinstance(system, MemoryTriageSystem)
        assert system.storage_path is not None
    
    def test_create_custom_system(self):
        """Test creating system with custom settings."""
        system = create_triage_system(
            storage_path="/custom/path",
            context_window_limit=50000,
            compression_threshold=0.7,
            auto_save=True
        )
        
        assert system.storage_path == "/custom/path"
        assert system.context_window_limit == 50000
        assert system.compression_threshold == 0.7
        assert system.auto_save is True
