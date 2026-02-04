"""Tests for Memory Query System."""

import pytest
import os
import tempfile
from pathlib import Path
from memory_query import MemoryQuery


@pytest.fixture
def temp_memory_dir():
    """Create a temporary memory directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test daily logs
        log1 = Path(tmpdir) / "2026-02-01.md"
        log1.write_text("""# Daily Log 2026-02-01

## What I Built
- Built a new feature for taste profiling
- Shipped tests for rejection taxonomy

## What I Learned
- ASCII art makes data more memorable
- Progress bars communicate quantity instantly

## Notes
Great day for building!
""")
        
        log2 = Path(tmpdir) / "2026-02-02.md"
        log2.write_text("""# Daily Log 2026-02-02

## Status
Working on memory query system

## Actions
- Designed entity extraction
- Implemented full-text search

## Reflections
Memory is the foundation of identity.
""")
        
        log3 = Path(tmpdir) / "2026-02-03.md"
        log3.write_text("""# Daily Log 2026-02-03

## Build
Launched the taste signature feature

## Moltbook
Posted about rejection taxonomy
Upvoted interesting posts from other agents
""")
        
        # Create a non-markdown file (should be skipped)
        json_file = Path(tmpdir) / "data.json"
        json_file.write_text('{"test": "skip this file"}')
        
        yield tmpdir


class TestMemoryQuery:
    """Test MemoryQuery class."""
    
    def test_search_finds_term(self, temp_memory_dir):
        """Test that search finds matching terms."""
        q = MemoryQuery(memory_dir=temp_memory_dir)
        results = q.search("taste")
        
        assert len(results) >= 1
        # Check result structure
        assert all('file' in r for r in results)
        assert all('content' in r for r in results)
        
    def test_search_case_insensitive(self, temp_memory_dir):
        """Test that search is case insensitive."""
        q = MemoryQuery(memory_dir=temp_memory_dir)
        results_lower = q.search("taste")
        results_upper = q.search("TASTE")
        
        assert len(results_lower) == len(results_upper)
        
    def test_search_only_includes_markdown_files(self, temp_memory_dir):
        """Test that search only includes markdown files."""
        q = MemoryQuery(memory_dir=temp_memory_dir)
        results = q.search("test")
        
        # All results should be from .md files
        for r in results:
            assert r['file'].endswith('.md'), f"Expected .md file, got {r['file']}"
        
    def test_extract_entities(self, temp_memory_dir):
        """Test entity extraction."""
        q = MemoryQuery(memory_dir=temp_memory_dir)
        entities = q.extract_entities()
        
        assert 'entities' in entities
        assert 'projects' in entities
        assert 'concepts' in entities
        
    def test_get_timeline(self, temp_memory_dir):
        """Test timeline generation."""
        q = MemoryQuery(memory_dir=temp_memory_dir)
        timeline = q.get_timeline(days=30)
        
        assert len(timeline) >= 1
        # Check timeline structure
        for entry in timeline:
            assert 'date' in entry
            assert 'summary' in entry
            assert 'actions' in entry
            
    def test_timeline_ordering(self, temp_memory_dir):
        """Test that timeline is ordered by date descending."""
        q = MemoryQuery(memory_dir=temp_memory_dir)
        timeline = q.get_timeline(days=30)
        
        if len(timeline) >= 2:
            dates = [entry['date'] for entry in timeline]
            assert dates == sorted(dates, reverse=True)
            
    def test_find_related(self, temp_memory_dir):
        """Test find_related method."""
        q = MemoryQuery(memory_dir=temp_memory_dir)
        results = q.find_related("memory", max_results=5)
        
        assert len(results) <= 5
        
    def test_get_concept_frequency(self, temp_memory_dir):
        """Test concept frequency tracking."""
        q = MemoryQuery(memory_dir=temp_memory_dir)
        freq = q.get_concept_frequency()
        
        assert isinstance(freq, dict)
        # 'memory' should appear in at least one log
        if 'memory' in freq:
            assert len(freq['memory']) >= 1
            
    def test_search_with_limit(self, temp_memory_dir):
        """Test search result limiting."""
        q = MemoryQuery(memory_dir=temp_memory_dir)
        results = q.search("the", max_results=3)
        
        assert len(results) <= 3


class TestMemoryQueryCLI:
    """Test CLI integration."""
    
    def test_query_module_runs(self, temp_memory_dir):
        """Test that the module can be imported and run."""
        import sys
        sys.argv = ['memory_query.py', 'search', 'taste']
        
        # This should not raise
        from memory_query import main
        # Just verify it can be called - full CLI test would need more setup
        assert main is not None
