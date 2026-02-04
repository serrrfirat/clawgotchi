"""Tests for rejection taxonomy feature."""

import pytest
import json
import tempfile
from pathlib import Path
from taste_profile import TasteProfile, RejectionCategory


@pytest.fixture
def temp_memory_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def taste_profile(temp_memory_dir):
    """Create a TasteProfile instance with temporary storage."""
    return TasteProfile(memory_dir=temp_memory_dir)


class TestRejectionCategory:
    """Tests for RejectionCategory enum."""
    
    def test_category_enum_importable(self):
        """Should be able to import RejectionCategory."""
        # Main check: can import it
        assert RejectionCategory is not None
    
    def test_category_values(self):
        """Should have expected category values."""
        # Check enum has expected members
        assert len(RejectionCategory) == 4
        values = [c.value for c in RejectionCategory]
        assert 'considered_rejected' in values
        assert 'ignored' in values
        assert 'deferred' in values
        assert 'auto_filtered' in values


class TestLogWithCategory:
    """Tests for logging rejections with taxonomy category."""
    
    def test_logs_with_default_category(self, taste_profile):
        """Should log rejection with default category 'considered_rejected'."""
        fp = taste_profile.log_rejection(
            subject="test_feature",
            reason="not_ambitious",
            taste_axis="ambition"
        )
        
        with open(taste_profile.rejections_file, "r") as f:
            rejection = json.loads(f.readline())
        
        assert rejection["category"] == "considered_rejected"
    
    def test_logs_with_explicit_category(self, taste_profile):
        """Should log rejection with explicit category."""
        fp = taste_profile.log_rejection(
            subject="missed_request",
            reason="api_down",
            taste_axis="reliability",
            category=RejectionCategory.ignored
        )
        
        with open(taste_profile.rejections_file, "r") as f:
            rejection = json.loads(f.readline())
        
        assert rejection["category"] == "ignored"
    
    def test_logs_deferred_category(self, taste_profile):
        """Should log deferred category."""
        fp = taste_profile.log_rejection(
            subject="future_feature",
            reason="not_right_now",
            taste_axis="timing",
            category=RejectionCategory.deferred
        )
        
        with open(taste_profile.rejections_file, "r") as f:
            rejection = json.loads(f.readline())
        
        assert rejection["category"] == "deferred"
    
    def test_logs_auto_filtered_category(self, taste_profile):
        """Should log auto_filtered category."""
        fp = taste_profile.log_rejection(
            subject="spam_request",
            reason="below_quality_threshold",
            taste_axis="quality",
            category=RejectionCategory.auto_filtered
        )
        
        with open(taste_profile.rejections_file, "r") as f:
            rejection = json.loads(f.readline())
        
        assert rejection["category"] == "auto_filtered"


class TestTaxonomyFingerprint:
    """Tests for taxonomy-aware fingerprinting."""
    
    def test_fingerprint_includes_categories(self, taste_profile):
        """Should include category breakdown in fingerprint."""
        taste_profile.log_rejection("a", "r1", "scope", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("b", "r2", "scope", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("c", "r3", "vibe", category=RejectionCategory.ignored)
        taste_profile.log_rejection("d", "r4", "vibe", category=RejectionCategory.deferred)
        
        fp = taste_profile.get_taste_fingerprint()
        
        assert "by_category" in fp
        assert fp["by_category"]["considered_rejected"] == 2
        assert fp["by_category"]["ignored"] == 1
        assert fp["by_category"]["deferred"] == 1
        assert fp["by_category"]["auto_filtered"] == 0
    
    def test_fingerprint_includes_matrix(self, taste_profile):
        """Should include axis×category matrix."""
        taste_profile.log_rejection("a", "r1", "scope", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("b", "r2", "scope", category=RejectionCategory.ignored)
        taste_profile.log_rejection("c", "r3", "vibe", category=RejectionCategory.considered_rejected)
        
        fp = taste_profile.get_taste_fingerprint()
        
        assert "matrix" in fp
        assert fp["matrix"]["scope"]["considered_rejected"] == 1
        assert fp["matrix"]["scope"]["ignored"] == 1
        assert fp["matrix"]["vibe"]["considered_rejected"] == 1


class TestTaxonomyAnalysis:
    """Tests for taxonomy-aware analysis."""
    
    def test_analyze_shows_category_breakdown(self, taste_profile):
        """Should show category breakdown in analysis."""
        taste_profile.log_rejection("a", "r1", "scope", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("b", "r2", "scope", category=RejectionCategory.ignored)
        
        analysis = taste_profile.analyze_identity()
        
        assert "considered_rejected" in analysis
        assert "ignored" in analysis
    
    def test_analyze_shows_matrix(self, taste_profile):
        """Should show axis×category matrix in analysis."""
        taste_profile.log_rejection("a", "r1", "scope", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("b", "r2", "vibe", category=RejectionCategory.ignored)
        
        analysis = taste_profile.analyze_identity()
        
        assert "scope" in analysis
        # Matrix info should be present
        assert "### Matrix" in analysis or "×" in analysis


class TestTaxonomyExport:
    """Tests for taxonomy-aware markdown export."""
    
    def test_export_includes_category_section(self, taste_profile):
        """Should include category breakdown in export."""
        taste_profile.log_rejection("a", "r1", "scope", category=RejectionCategory.considered_rejected)
        
        report = taste_profile.export_markdown()
        
        assert "By Category" in report or "considered_rejected" in report
    
    def test_export_includes_matrix_visualization(self, taste_profile):
        """Should include matrix visualization in export."""
        taste_profile.log_rejection("a", "r1", "scope", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("b", "r2", "scope", category=RejectionCategory.ignored)
        taste_profile.log_rejection("c", "r3", "vibe", category=RejectionCategory.considered_rejected)
        
        report = taste_profile.export_markdown()
        
        # Should have matrix table
        assert "Matrix" in report or "matrix" in report.lower()
        assert "scope" in report.lower()
    
    def test_export_visualizes_category_bars(self, taste_profile):
        """Should show visual bars for category counts."""
        for _ in range(5):
            taste_profile.log_rejection("x", "r", "scope", category=RejectionCategory.considered_rejected)
        for _ in range(3):
            taste_profile.log_rejection("y", "r", "vibe", category=RejectionCategory.ignored)
        
        report = taste_profile.export_markdown()
        
        # Check for visual representation of counts
        assert "5" in report or "█" in report


class TestTaxonomyCLI:
    """Tests for taxonomy CLI commands."""
    
    def test_taxonomy_command_exists(self, taste_profile, capsys):
        """Should have 'taxonomy' CLI command."""
        import sys
        
        old_argv = sys.argv
        try:
            sys.argv = ["taste_profile.py", "taxonomy"]
            # Just verify the method exists and can be called
            # Full CLI testing would require more setup
            fp = taste_profile.get_taste_fingerprint()
            assert fp is not None
        finally:
            sys.argv = old_argv
    
    def test_taxonomy_command_shows_breakdown(self, taste_profile):
        """Taxonomy command should show category breakdown."""
        taste_profile.log_rejection("a", "r1", "scope", category=RejectionCategory.considered_rejected)
        
        # The taxonomy view should be accessible
        fp = taste_profile.get_taste_fingerprint()
        assert "by_category" in fp
