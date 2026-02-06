"""Tests for Memory Quality Scorer - Analyzes memory files for quality signals."""

import pytest
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path

from clawgotchi.resilience.memory_quality import (
    QualityDimension,
    QualityScore,
    MemoryQualityAnalyzer,
    QualityFinding,
    analyze_memory_quality
)


class TestQualityDimension:
    """Test QualityDimension enum."""

    def test_dimension_values(self):
        """Test quality dimension enum values."""
        assert QualityDimension.RECENCY.value == "recency"
        assert QualityDimension.ENTROPY.value == "entropy"
        assert QualityDimension.ACTIONABILITY.value == "actionability"
        assert QualityDimension.COHERENCE.value == "coherence"
        assert QualityDimension.DUPLICATION.value == "duplication"


class TestQualityScore:
    """Test QualityScore dataclass."""

    def test_score_creation(self):
        """Create a quality score."""
        score = QualityScore(
            dimension=QualityDimension.RECENCY,
            value=0.75,
            weight=1.0,
            finding="Recent activity detected"
        )
        assert score.dimension == QualityDimension.RECENCY
        assert score.value == 0.75
        assert score.weight == 1.0
        assert score.finding == "Recent activity detected"

    def test_weighted_score(self):
        """Calculate weighted score."""
        score = QualityScore(
            dimension=QualityDimension.RECENCY,
            value=0.5,
            weight=0.3,
            finding="Old content"
        )
        assert abs(score.weighted_value - 0.15) < 0.001


class TestMemoryQualityAnalyzer:
    """Test MemoryQualityAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory_file = Path(self.temp_dir) / "MEMORY.md"
        self.analyzer = MemoryQualityAnalyzer()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_empty_file(self):
        """Analyze an empty memory file."""
        self.memory_file.write_text("")
        result = self.analyzer.analyze(self.memory_file)
        assert result.overall_score < 0.3  # Low but not zero
        assert len(result.dimension_scores) == 5
        assert len(result.findings) >= 3  # Multiple findings

    def test_analyze_minimal_content(self):
        """Analyze minimal content."""
        content = "Test"
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        assert result.overall_score > 0

    def test_recency_score_recent(self):
        """Test recency scoring for recent content."""
        content = f"# MEMORY.md\n\nLast updated: {datetime.now().isoformat()}"
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        recency_score = next(
            s for s in result.dimension_scores 
            if s.dimension == QualityDimension.RECENCY
        )
        assert recency_score.value >= 0.8

    def test_recency_score_stale(self):
        """Test recency scoring for stale content."""
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        content = f"# MEMORY.md\n\nLast updated: {old_date}"
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        recency_score = next(
            s for s in result.dimension_scores 
            if s.dimension == QualityDimension.RECENCY
        )
        assert recency_score.value < 0.3

    def test_entropy_score_diverse(self):
        """Test entropy scoring for diverse content."""
        content = """# Topics

- Built a new feature for user authentication
- Fixed critical bug in payment processing
- Added machine learning model for recommendations
- Refactored database schema for better performance
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        entropy_score = next(
            s for s in result.dimension_scores 
            if s.dimension == QualityDimension.ENTROPY
        )
        assert entropy_score.value > 0.5

    def test_entropy_score_repetitive(self):
        """Test entropy scoring for repetitive content."""
        content = """# Repetitive

Word for word same thing again and again
Word for word same thing again and again
Word for word same thing again and again
Word for word same thing again and again
Word for word same thing again and again
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        entropy_score = next(
            s for s in result.dimension_scores 
            if s.dimension == QualityDimension.ENTROPY
        )
        assert entropy_score.value < 0.5

    def test_actionability_score_with_actions(self):
        """Test actionability scoring for content with actions."""
        content = """# TODO

- [ ] Build new feature (priority: high)
- [x] Fix bug in user auth
- [ ] Review pull request
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        action_score = next(
            s for s in result.dimension_scores 
            if s.dimension == QualityDimension.ACTIONABILITY
        )
        assert action_score.value >= 0.5

    def test_actionability_score_no_actions(self):
        """Test actionability scoring for content without actions."""
        content = """# Notes

Just some notes about things that happened.
No action items or tasks mentioned.
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        action_score = next(
            s for s in result.dimension_scores 
            if s.dimension == QualityDimension.ACTIONABILITY
        )
        assert action_score.value < 0.5

    def test_duplication_score_unique(self):
        """Test duplication scoring for unique content."""
        content = """# Memory

1. Built feature Alpha
2. Fixed bug in Beta
3. Added user profile
4. Refactored API endpoints
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        dup_score = next(
            s for s in result.dimension_scores 
            if s.dimension == QualityDimension.DUPLICATION
        )
        assert dup_score.value >= 0.7

    def test_duplication_score_repetitive(self):
        """Test duplication scoring for repetitive content."""
        content = """# Memory

Built feature X
Built feature X
Built feature X
Built feature X
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        dup_score = next(
            s for s in result.dimension_scores 
            if s.dimension == QualityDimension.DUPLICATION
        )
        assert dup_score.value < 0.8

    def test_coherence_score_coherent(self):
        """Test coherence scoring for coherent content."""
        content = """# Project Alpha

## Goal
Build a new feature for user authentication.

## Progress
- Completed OAuth integration
- Added two-factor auth
- Fixed session management

## Next Steps
- User profile management
- API documentation
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        coherence_score = next(
            s for s in result.dimension_scores 
            if s.dimension == QualityDimension.COHERENCE
        )
        assert coherence_score.value >= 0.6

    def test_overall_score_calculation(self):
        """Test overall score calculation."""
        content = """# Quality Memory

Last updated: 2026-02-06

- Built new feature
- Fixed bugs
- Added tests
- User is happy
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        assert 0.0 <= result.overall_score <= 1.0
        assert result.overall_score >= 0.5

    def test_get_quality_report(self):
        """Generate quality report."""
        content = """# Memory Report

Last updated: 2026-02-06

Recent activities and insights.
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        report = self.analyzer.get_report(result)
        
        assert "Quality Analysis Report" in report.title
        assert report.overall_score > 0

    def test_findings_generation(self):
        """Test that findings are generated."""
        content = """# Critical Issue

Last updated: 2020-01-01
Same thing again and again and again
"""
        self.memory_file.write_text(content)
        result = self.analyzer.analyze(self.memory_file)
        
        # Should have findings for low-scoring dimensions
        low_scores = [s for s in result.dimension_scores if s.value < 0.5]
        assert len(low_scores) > 0


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_analyze_memory_quality_function(self):
        """Test the convenience function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test Memory\n\n- Built feature\n- Fixed bug\n")
            f.flush()
            
            result = analyze_memory_quality(f.name)
            assert result.overall_score > 0
            
            import os
            os.unlink(f.name)


class TestIntegration:
    """Integration tests for the analyzer."""

    def test_full_analysis_workflow(self):
        """Test complete analysis workflow."""
        content = """# CLAW - Development Log

**Date:** 2026-02-06
**Session:** Heartbeat #699

## Status
- Tests: 123 passing
- Moltbook: Connected

## Recent Work
- Built Memory Audit Utility with TDD
- Repository cleanup - removed tracked __pycache__ files
- Verifying assumptions and curating memories

## Insights
Context scarcity is the new divide. The competitive edge lies in unique context.

## Next Steps
- Continue heartbeat development
- Ship small features
- Post to Moltbook
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            f_path = Path(f.name)
            
            analyzer = MemoryQualityAnalyzer()
            result = analyzer.analyze(f_path)
            report = analyzer.get_report(result)
            
            # Should have good scores across dimensions
            assert result.overall_score >= 0.6
            
            # Cleanup
            import os
            os.unlink(f.name)
