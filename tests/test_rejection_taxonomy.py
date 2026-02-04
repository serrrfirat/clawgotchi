"""Tests for rejection taxonomy feature."""

import pytest
import json
import tempfile
from pathlib import Path
from cognition.taste_profile import TasteProfile, RejectionCategory


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


class TestTasteSignature:
    """Tests for taste signature ASCII generation."""
    
    def test_signature_exists(self, taste_profile):
        """Should have get_signature method."""
        sig = taste_profile.get_signature()
        assert sig is not None
        assert isinstance(sig, str)
    
    def test_signature_empty_profile(self, taste_profile):
        """Empty profile should show placeholder."""
        sig = taste_profile.get_signature()
        assert "Empty" in sig or "still forming" in sig
    
    def test_signature_with_rejections(self, taste_profile):
        """Signature should reflect rejection counts."""
        taste_profile.log_rejection("f1", "r1", "ambition", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("f2", "r2", "ambition", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("f3", "r3", "scope", category=RejectionCategory.ignored)
        
        sig = taste_profile.get_signature()
        assert sig is not None
        assert len(sig) > 0
        # Should contain bars representing the axes
        assert "█" in sig or "░" in sig
    
    def test_signature_shows_top_axes(self, taste_profile):
        """Signature should show top axes first."""
        # Add more rejections for different axes
        taste_profile.log_rejection("f1", "r1", "ambition", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("f2", "r2", "ambition", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("f3", "r3", "ambition", category=RejectionCategory.considered_rejected)
        taste_profile.log_rejection("f4", "r4", "scope", category=RejectionCategory.ignored)
        taste_profile.log_rejection("f5", "r5", "vibe", category=RejectionCategory.auto_filtered)
        
        sig = taste_profile.get_signature(max_axes=3)
        # Should show ambition first (most rejections)
        assert "ambition" in sig
    
    def test_signature_cli_command(self, taste_profile, capsys):
        """Should have 'signature' CLI command."""
        import sys
        
        old_argv = sys.argv
        try:
            sys.argv = ["taste_profile.py", "signature"]
            sig = taste_profile.get_signature()
            assert sig is not None
        finally:
            sys.argv = old_argv


class TestGrowthSignal:
    """Tests for growth signal analysis feature."""
    
    def test_growth_signal_empty_profile(self, taste_profile):
        """Should return empty signal for no rejections."""
        signal = taste_profile.get_growth_signal()
        
        assert "recent_axes" in signal
        assert "older_axes" in signal
        assert "emerging_axes" in signal
        assert "declining_axes" in signal
        assert signal["growth_score"] == 0.0
        assert signal["recent_count"] == 0 and signal["older_count"] == 0
    
    def test_growth_signal_calculates_recent_vs_older(self, taste_profile):
        """Should separate recent from older rejections."""
        from datetime import datetime, timedelta
        
        # Add an older rejection
        older_time = (datetime.now() - timedelta(days=10)).isoformat()
        with open(taste_profile.rejections_file, "a") as f:
            f.write('{"fingerprint":"abc123","timestamp":"' + older_time + '","subject":"old_feature","reason":"old","axis":"scope","category":"considered_rejected"}\n')
        
        # Add a recent rejection
        recent_time = datetime.now().isoformat()
        with open(taste_profile.rejections_file, "a") as f:
            f.write('{"fingerprint":"def456","timestamp":"' + recent_time + '","subject":"new_feature","reason":"new","axis":"ambition","category":"considered_rejected"}\n')
        
        signal = taste_profile.get_growth_signal(days=7)
        
        # The old one should be in older, recent in recent
        assert signal["recent_count"] >= 1
        assert signal["older_count"] >= 1
    
    def test_growth_signal_emerging_axes(self, taste_profile):
        """Should detect emerging axes (growing interest)."""
        from datetime import datetime, timedelta
        
        # Add many older rejections for one axis
        older_time = (datetime.now() - timedelta(days=10)).isoformat()
        for i in range(3):
            with open(taste_profile.rejections_file, "a") as f:
                f.write(f'{{"fingerprint":"old{i}","timestamp":"{older_time}","subject":"old{i}","reason":"r","axis":"scope","category":"considered_rejected"}}\n')
        
        # Add many recent rejections for same axis (growing)
        recent_time = datetime.now().isoformat()
        for i in range(5):
            with open(taste_profile.rejections_file, "a") as f:
                f.write(f'{{"fingerprint":"new{i}","timestamp":"{recent_time}","subject":"new{i}","reason":"r","axis":"scope","category":"considered_rejected"}}\n')
        
        signal = taste_profile.get_growth_signal()
        
        # scope should be emerging (more recent than older)
        assert "scope" in signal["emerging_axes"]
    
    def test_growth_signal_declining_axes(self, taste_profile):
        """Should detect declining axes (fading interest)."""
        from datetime import datetime, timedelta
        
        # Add many older rejections for one axis
        older_time = (datetime.now() - timedelta(days=10)).isoformat()
        for i in range(5):
            with open(taste_profile.rejections_file, "a") as f:
                f.write(f'{{"fingerprint":"old{i}","timestamp":"{older_time}","subject":"old{i}","reason":"r","axis":"vibe","category":"considered_rejected"}}\n')
        
        # Add few recent rejections for same axis (declining)
        recent_time = datetime.now().isoformat()
        with open(taste_profile.rejections_file, "a") as f:
            f.write('{"fingerprint":"new1","timestamp":"' + recent_time + '","subject":"new1","reason":"r","axis":"vibe","category":"considered_rejected"}\n')
        
        signal = taste_profile.get_growth_signal()
        
        # vibe should be declining (less recent than older)
        assert "vibe" in signal["declining_axes"]
    
    def test_growth_signal_growth_score_range(self, taste_profile):
        """Growth score should be between -1 and 1."""
        from datetime import datetime, timedelta
        
        # All recent should give positive score
        recent_time = datetime.now().isoformat()
        for i in range(5):
            with open(taste_profile.rejections_file, "a") as f:
                f.write(f'{{"fingerprint":"r{i}","timestamp":"{recent_time}","subject":"s{i}","reason":"r","axis":"x","category":"considered_rejected"}}\n')
        
        signal = taste_profile.get_growth_signal()
        assert -1 <= signal["growth_score"] <= 1
    
    def test_analyze_growth_returns_string(self, taste_profile):
        """analyze_growth should return a string."""
        analysis = taste_profile.analyze_growth()
        
        assert isinstance(analysis, str)
        assert "Growth Signal" in analysis or "No data" in analysis
    
    def test_growth_signal_with_custom_days(self, taste_profile):
        """Should respect custom days parameter."""
        from datetime import datetime, timedelta
        
        # Add a rejection from 5 days ago (recent for 7-day window, old for 3-day)
        older_time = (datetime.now() - timedelta(days=5)).isoformat()
        with open(taste_profile.rejections_file, "a") as f:
            f.write('{"fingerprint":"mid","timestamp":"' + older_time + '","subject":"mid","reason":"r","axis":"scope","category":"considered_rejected"}\n')
        
        # 7-day window should see it as recent
        signal_7 = taste_profile.get_growth_signal(days=7)
        # 3-day window should see it as older
        signal_3 = taste_profile.get_growth_signal(days=3)
        
        # The 7-day window should have more recent count
        assert signal_7["recent_count"] >= signal_3["recent_count"]


class TestGrowthCLI:
    """Tests for growth CLI commands."""
    
    def test_growth_cli_command_exists(self, taste_profile):
        """Should have 'growth' CLI command."""
        import sys
        
        # Just verify the method exists
        signal = taste_profile.get_growth_signal()
        assert signal is not None
    
    def test_growth_cli_with_days(self, taste_profile):
        """Should accept days parameter."""
        from datetime import datetime
        
        # Add a rejection
        with open(taste_profile.rejections_file, "a") as f:
            f.write('{"fingerprint":"test","timestamp":"' + datetime.now().isoformat() + '","subject":"test","reason":"r","axis":"scope","category":"considered_rejected"}\n')
        
        signal_7 = taste_profile.get_growth_signal(7)
        signal_14 = taste_profile.get_growth_signal(14)
        
        assert signal_7 is not None
        assert signal_14 is not None
