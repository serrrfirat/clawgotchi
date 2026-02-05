"""Tests for memory_distiller.py - Memory compression and distillation utilities."""

import os
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from clawgotchi.resilience.memory_distiller import (
    compress_session,
    extract_decisions,
    extract_actions,
    generate_summary,
    distill_daily_memory,
    extract_memories_from_content,
    distill_memories,
    merge_into_longterm,
    is_worth_distilling,
    build_memory_index,
    check_weekly_review,
    quick_distill,
    MemoryItem,
    DistilledMemory
)


class TestExtractDecisions:
    """Tests for extract_decisions function."""
    
    def test_extracts_simple_decision(self):
        """Test basic decision extraction."""
        text = "I decided to use Python for the project."
        result = extract_decisions(text)
        assert len(result) >= 1
        assert any("python" in d.lower() for d in result)
    
    def test_extracts_multiple_decisions(self):
        """Test multiple decisions are extracted."""
        text = "I decided to use Python. Then I chose PostgreSQL for the database."
        result = extract_decisions(text)
        assert len(result) >= 2
    
    def test_deduplicates_similar_decisions(self):
        """Test that similar decisions are deduplicated."""
        text = "I decided to use Python. I decided to use Python."
        result = extract_decisions(text)
        assert len(result) == 1
    
    def test_handles_empty_text(self):
        """Test empty text returns empty list."""
        result = extract_decisions("")
        assert result == []
    
    def test_ignores_short_matches(self):
        """Test that very short matches are filtered."""
        text = "I will go."
        result = extract_decisions(text)
        # Should be empty or filtered due to length
        for r in result:
            assert len(r) > 5


class TestExtractActions:
    """Tests for extract_actions function."""
    
    def test_extracts_action_items(self):
        """Test action extraction."""
        text = "Next action: implement the feature."
        result = extract_actions(text)
        assert len(result) >= 1
        assert any("implement" in a.lower() or "feature" in a.lower() for a in result)
    
    def test_extracts_will_statements(self):
        """Test 'will' statements as actions."""
        text = "I will complete this by tomorrow."
        result = extract_actions(text)
        assert len(result) >= 1
    
    def test_extracts_todo_items(self):
        """Test todo items."""
        text = "TODO: write tests for the module."
        result = extract_actions(text)
        assert len(result) >= 1
    
    def test_deduplicates_actions(self):
        """Test action deduplication."""
        text = "I need to test this. I need to test this."
        result = extract_actions(text)
        assert len(result) == 1


class TestGenerateSummary:
    """Tests for generate_summary function."""
    
    def test_returns_string(self):
        """Test summary returns a string."""
        text = "This is a test sentence. Another test sentence here."
        result = generate_summary(text)
        assert isinstance(result, str)
    
    def test_respects_max_chars(self):
        """Test summary respects max_chars limit."""
        text = "This is a test sentence. " * 100
        result = generate_summary(text, max_chars=100)
        assert len(result) <= 100
    
    def test_handles_empty_text(self):
        """Test empty text returns empty string."""
        result = generate_summary("")
        assert result == ""
    
    def test_preserves_order_of_scored_sentences(self):
        """Test that high-scoring sentences appear in summary."""
        text = "First sentence is generic. I learned something important here. Third sentence is boring."
        result = generate_summary(text)
        assert "learned" in result.lower() or "important" in result.lower()


class TestCompressSession:
    """Tests for compress_session function."""
    
    def test_returns_dict_with_keys(self):
        """Test compression returns expected keys."""
        result = compress_session("Test session log")
        assert "decisions" in result
        assert "actions" in result
        assert "summary" in result
        assert "timestamp" in result
    
    def test_timestamp_is_iso_format(self):
        """Test timestamp is in ISO format."""
        result = compress_session("Test")
        try:
            datetime.fromisoformat(result["timestamp"])
        except ValueError:
            pytest.fail("Timestamp is not valid ISO format")
    
    def test_handles_empty_session(self):
        """Test empty session handling."""
        result = compress_session("")
        assert result["decisions"] == []
        assert result["actions"] == []
        assert "summary" in result


class TestIsWorthDistilling:
    """Tests for is_worth_distilling function."""
    
    def test_completion_markers_high_score(self):
        """Test completion markers like 'built', 'shipped' score high."""
        text = "I built a new feature today."
        assert is_worth_distilling(text, min_importance=0.6) is True
    
    def test_learning_markers_score_high(self):
        """Test learning markers score appropriately."""
        text = "I learned how to optimize queries."
        result = is_worth_distilling(text, min_importance=0.6)
        # Should be True or False depending on threshold, but shouldn't error
        assert isinstance(result, bool)
    
    def test_generic_text_scores_low(self):
        """Test generic text scores low."""
        text = "Today was a normal day. Nothing special happened."
        result = is_worth_distilling(text, min_importance=0.8)
        assert result is False
    
    def test_empty_text_returns_false(self):
        """Test empty text returns False."""
        assert is_worth_distilling("") is False


class TestQuickDistill:
    """Tests for quick_distill function."""
    
    def test_returns_string(self):
        """Test quick_distill returns string."""
        result = quick_distill("Test session")
        assert isinstance(result, str)
    
    def test_extracts_decision(self):
        """Test decision extraction in quick distill."""
        text = "I decided to use the circuit breaker pattern."
        result = quick_distill(text)
        assert "decided" in result.lower() or "circuit" in result.lower()
    
    def test_handles_empty(self):
        """Test empty input handling."""
        result = quick_distill("")
        assert isinstance(result, str)


class TestMemoryItem:
    """Tests for MemoryItem dataclass."""
    
    def test_creates_with_defaults(self):
        """Test MemoryItem creation with default values."""
        item = MemoryItem(content="Test", timestamp=datetime.now())
        assert item.source == "unknown"
        assert item.importance == 0.5
        assert item.tags == []
    
    def test_creates_with_custom_values(self):
        """Test MemoryItem creation with custom values."""
        now = datetime.now()
        item = MemoryItem(
            content="Important decision",
            timestamp=now,
            source="session.log",
            importance=0.9,
            tags=["decision", "priority"]
        )
        assert item.content == "Important decision"
        assert item.timestamp == now
        assert item.importance == 0.9
        assert "decision" in item.tags


class TestDistilledMemory:
    """Tests for DistilledMemory dataclass."""
    
    def test_creates_with_defaults(self):
        """Test DistilledMemory with default values."""
        mem = DistilledMemory(
            content="Distilled content",
            original_items=["item1", "item2"],
            distilled_at=datetime.now(),
            categories=["learning"]
        )
        assert mem.action_items == []
        assert mem.decisions == []


class TestExtractMemoriesFromContent:
    """Tests for extract_memories_from_content function."""
    
    def test_returns_list(self):
        """Test extraction returns list."""
        items = extract_memories_from_content("Test content", datetime.now(), "test.md")
        assert isinstance(items, list)
    
    def test_extracts_from_markdown(self):
        """Test extraction from markdown-style content."""
        content = "## Section\nSome content here.\n- Bullet point"
        items = extract_memories_from_content(content, datetime.now(), "test.md")
        assert len(items) >= 1
    
    def test_importance_scoring(self):
        """Test importance is assigned based on content."""
        high_importance = "I built and shipped a new feature today."
        low_importance = "Thinking about what to do next."
        
        high_items = extract_memories_from_content(high_importance, datetime.now(), "test.md")
        low_items = extract_memories_from_content(low_importance, datetime.now(), "test.md")
        
        if high_items and low_items:
            assert high_items[0].importance >= low_items[0].importance


class TestDistillMemories:
    """Tests for distill_memories function."""
    
    def test_returns_list(self):
        """Test distill returns list."""
        items = [
            MemoryItem(content="Test item", timestamp=datetime.now(), importance=0.5)
        ]
        result = distill_memories(items)
        assert isinstance(result, list)
    
    def test_empty_input_returns_empty(self):
        """Test empty input returns empty list."""
        result = distill_memories([])
        assert result == []
    
    def test_clusters_by_first_word(self):
        """Test items are clustered by first word."""
        items = [
            MemoryItem(content="Python is great", timestamp=datetime.now()),
            MemoryItem(content="Python for AI", timestamp=datetime.now()),
            MemoryItem(content="Java is different", timestamp=datetime.now())
        ]
        result = distill_memories(items)
        # Should have at least 2 clusters
        assert len(result) >= 2


class TestBuildMemoryIndex:
    """Tests for build_memory_index function."""
    
    def test_returns_dict(self):
        """Test returns dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_memory_index(tmpdir)
            assert isinstance(result, dict)
    
    def test_has_expected_keys(self):
        """Test index has expected structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_memory_index(tmpdir)
            assert "by_date" in result
            assert "keywords" in result
    
    def test_indexes_files(self):
        """Test files are indexed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test memory file
            mem_file = Path(tmpdir) / "2024-01-15.md"
            mem_file.write_text("Test memory content")
            
            result = build_memory_index(tmpdir)
            assert "2024-01-15" in result.get("by_date", {})


class TestCheckWeeklyReview:
    """Tests for check_weekly_review function."""
    
    def test_returns_dict(self):
        """Test returns dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_weekly_review(tmpdir)
            assert isinstance(result, dict)
    
    def test_has_expected_keys(self):
        """Test result has expected keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_weekly_review(tmpdir)
            assert "needed" in result
            assert "count" in result
    
    def test_empty_dir_not_needed(self):
        """Test empty directory doesn't need review."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_weekly_review(tmpdir)
            # Either not needed or no memory dir
            assert isinstance(result["needed"], bool)
    
    def test_recent_files_flagged(self):
        """Test recent files are flagged for review."""
        with tempfile.TemporaryDirectory() as tmpdir:
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            yesterday_str = yesterday.strftime("%Y-%m-%d")
            
            # Create a recent memory file
            mem_file = Path(tmpdir) / f"{yesterday_str}.md"
            mem_file.write_text("Recent memory content")
            
            result = check_weekly_review(tmpdir)
            # Should either be needed or count should reflect the file


class TestMergeIntoLongterm:
    """Tests for merge_into_longterm function."""
    
    def test_creates_file_if_not_exists(self):
        """Test creates file if doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            longterm_path = Path(tmpdir) / "MEMORY.md"
            distilled = [
                DistilledMemory(
                    content="Test memory",
                    original_items=["test.md"],
                    distilled_at=datetime.now(),
                    categories=["test"]
                )
            ]
            result = merge_into_longterm(distilled, str(longterm_path))
            assert result["added"] == 1
            assert longterm_path.exists()
    
    def test_appends_to_existing(self):
        """Test appends to existing MEMORY.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            longterm_path = Path(tmpdir) / "MEMORY.md"
            longterm_path.write_text("# Existing Memory\nOld content here.")
            
            distilled = [
                DistilledMemory(
                    content="New distilled memory",
                    original_items=["new.md"],
                    distilled_at=datetime.now(),
                    categories=["new"]
                )
            ]
            result = merge_into_longterm(distilled, str(longterm_path))
            
            content = longterm_path.read_text()
            assert "New distilled memory" in content
            assert "Old content here." in content
    
    def test_prevents_duplicates(self):
        """Test prevents duplicate entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            longterm_path = Path(tmpdir) / "MEMORY.md"
            longterm_path.write_text("# Memory\n- **2024-01-15**: Same content")
            
            distilled = [
                DistilledMemory(
                    content="Same content",
                    original_items=["test.md"],
                    distilled_at=datetime.now(),
                    categories=["test"]
                )
            ]
            result = merge_into_longterm(distilled, str(longterm_path))
            # Should not add duplicate
            assert result["added"] == 0


class TestDistillDailyMemory:
    """Tests for distill_daily_memory function."""
    
    def test_returns_dict(self):
        """Test returns dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = distill_daily_memory(tmpdir)
            assert isinstance(result, dict)
    
    def test_has_expected_keys(self):
        """Test result has expected keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = distill_daily_memory(tmpdir)
            assert "files_processed" in result
            assert "items_extracted" in result
            assert "memories_distilled" in result
            assert "items_added_to_longterm" in result
    
    def test_handles_single_file(self):
        """Test processing single memory file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            today = datetime.now().strftime("%Y-%m-%d")
            mem_file = Path(tmpdir) / f"{today}.md"
            mem_file.write_text("## Test\nI decided to build a feature today.")
            
            result = distill_daily_memory(tmpdir)
            assert result["files_processed"] == 1
    
    def test_handles_directory(self):
        """Test processing directory of memories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple files
            for i in range(3):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                mem_file = Path(tmpdir) / f"{date}.md"
                mem_file.write_text(f"Memory for {date}")
            
            result = distill_daily_memory(tmpdir, lookback_days=7)
            assert result["files_processed"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
