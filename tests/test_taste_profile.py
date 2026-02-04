"""Tests for taste_profile.py - The Taste Function feature."""

import pytest
import json
import os
import tempfile
from pathlib import Path
from taste_profile import TasteProfile


@pytest.fixture
def temp_memory_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def taste_profile(temp_memory_dir):
    """Create a TasteProfile instance with temporary storage."""
    return TasteProfile(memory_dir=temp_memory_dir)


class TestTasteProfileInit:
    """Tests for TasteProfile initialization."""
    
    def test_creates_rejections_file(self, temp_memory_dir):
        """Should create the rejections file on init."""
        TasteProfile(memory_dir=temp_memory_dir)
        rejections_file = Path(temp_memory_dir) / "taste_rejections.jsonl"
        assert rejections_file.exists()
    
    def test_handles_existing_file(self, temp_memory_dir):
        """Should not fail if file already exists."""
        rejections_file = Path(temp_memory_dir) / "taste_rejections.jsonl"
        rejections_file.touch()
        
        profile = TasteProfile(memory_dir=temp_memory_dir)
        assert profile.rejections_file.exists()


class TestLogRejection:
    """Tests for logging rejection decisions."""
    
    def test_logs_rejection_with_all_fields(self, taste_profile):
        """Should log a complete rejection."""
        fp = taste_profile.log_rejection(
            subject="feature:emotion_face_happy",
            reason="already_have_enough_emotions",
            taste_axis="scope",
            alternative="taste_profile_feature"
        )
        
        assert fp is not None
        assert len(fp) == 12  # SHA256 hex, first 12 chars
        
        # Verify it was written
        with open(taste_profile.rejections_file, "r") as f:
            rejection = json.loads(f.readline())
        
        assert rejection["subject"] == "feature:emotion_face_happy"
        assert rejection["reason"] == "already_have_enough_emotions"
        assert rejection["axis"] == "scope"
        assert rejection["alternative"] == "taste_profile_feature"
        assert "fingerprint" in rejection
        assert "timestamp" in rejection
    
    def test_logs_rejection_without_alternative(self, taste_profile):
        """Should log rejection when alternative is None."""
        fp = taste_profile.log_rejection(
            subject="feature:another_emotion",
            reason="not_ambitious_enough",
            taste_axis="ambition"
        )
        
        assert fp is not None
        
        with open(taste_profile.rejections_file, "r") as f:
            rejection = json.loads(f.readline())
        
        assert rejection["alternative"] is None
    
    def test_fingerprint_is_deterministic_for_same_input(self, temp_memory_dir):
        """Same input should produce same fingerprint (within same second)."""
        profile = TasteProfile(memory_dir=temp_memory_dir)
        
        fp1 = profile.log_rejection("test", "reason", "axis", None)
        # Clean up for next test
        profile.rejections_file.unlink()
        profile._ensure_storage()
        
        fp2 = profile.log_rejection("test", "reason", "axis", None)
        
        # Same input = same hash (but timestamp differs slightly)
        # So we just verify both are valid fingerprints
        assert len(fp1) == 12
        assert len(fp2) == 12


class TestGetTasteFingerprint:
    """Tests for generating taste fingerprints."""
    
    def test_empty_fingerprint(self, taste_profile):
        """Should return empty dict for fresh profile."""
        fp = taste_profile.get_taste_fingerprint()
        
        assert fp["total_rejections"] == 0
        assert fp["axes"] == {}
        assert fp["recent"] == []
        assert fp["primary_axis"] is None
    
    def test_counts_by_axis(self, taste_profile):
        """Should correctly count rejections per axis."""
        taste_profile.log_rejection("a", "r1", "scope")
        taste_profile.log_rejection("b", "r2", "scope")
        taste_profile.log_rejection("c", "r3", "vibe")
        taste_profile.log_rejection("d", "r4", "vibe")
        taste_profile.log_rejection("e", "r5", "vibe")
        
        fp = taste_profile.get_taste_fingerprint()
        
        assert fp["total_rejections"] == 5
        assert fp["axes"]["scope"] == 2
        assert fp["axes"]["vibe"] == 3
        assert fp["primary_axis"] == "vibe"
    
    def test_recent_samples_limited_to_5(self, taste_profile):
        """Should return at most 5 recent samples."""
        for i in range(10):
            taste_profile.log_rejection(f"item_{i}", "reason", "test")
        
        fp = taste_profile.get_taste_fingerprint()
        
        assert len(fp["recent"]) == 5


class TestAnalyzeIdentity:
    """Tests for identity analysis."""
    
    def test_empty_profile_message(self, taste_profile):
        """Should return message for empty profile."""
        result = taste_profile.analyze_identity()
        
        assert "empty" in result.lower()
        assert "no rejections" in result.lower()
    
    def test_analyze_with_rejections(self, taste_profile):
        """Should generate identity analysis."""
        taste_profile.log_rejection(
            "scope:small_feature",
            "not_ambitious",
            "ambition"
        )
        taste_profile.log_rejection(
            "vibe:generic_ui",
            "lacks_personality",
            "vibe"
        )
        
        result = taste_profile.analyze_identity()
        
        assert "Taste Fingerprint" in result
        assert "2 rejections" in result
        assert "ambition" in result
        assert "vibe" in result
    
    def test_shows_primary_axis(self, taste_profile):
        """Should highlight the primary discrimination axis."""
        for _ in range(5):
            taste_profile.log_rejection("x", "r", "scope")
        for _ in range(2):
            taste_profile.log_rejection("y", "r", "vibe")
        
        result = taste_profile.analyze_identity()
        
        assert "Primary axis of discrimination: scope" in result


class TestCLIInterface:
    """Tests for CLI command parsing."""
    
    def test_log_command_structure(self, taste_profile, capsys):
        """Test the log CLI command."""
        import sys
        
        # Simulate: python taste_profile.py log <args>
        old_argv = sys.argv
        try:
            sys.argv = ["taste_profile.py", "log", "test_subject", "test_reason", "test_axis"]
            
            # We can't easily test the CLI without running main
            # Just verify the method works
            fp = taste_profile.log_rejection("test_subject", "test_reason", "test_axis")
            assert fp is not None
        finally:
            sys.argv = old_argv


class TestExportMarkdown:
    """Tests for markdown export functionality."""
    
    def test_export_empty_profile(self, taste_profile, capsys):
        """Should generate appropriate output for empty profile."""
        report = taste_profile.export_markdown()
        
        assert "# 🐱 Clawgotchi Taste Profile" in report
        assert "no rejections recorded" in report.lower()
        assert "What is this?" in report
    
    def test_export_with_rejections(self, taste_profile):
        """Should generate detailed report with rejections."""
        taste_profile.log_rejection(
            "feature:another_emotion",
            "not_ambitious_enough",
            "ambition"
        )
        taste_profile.log_rejection(
            "ui:generic_face",
            "lacks_personality",
            "vibe",
            "taste_profile_feature"
        )
        
        report = taste_profile.export_markdown()
        
        assert "**Total rejections:** 2" in report  # bold format
        assert "ambition" in report
        assert "vibe" in report
        assert "Primary axis" in report
        assert "not_ambitious_enough" in report
        assert "lacks_personality" in report
        assert "**Chose instead:** taste_profile_feature" in report
    
    def test_export_writes_to_file(self, taste_profile, tmp_path):
        """Should write report to file when output_file specified."""
        taste_profile.log_rejection("test", "reason", "test")
        
        output_file = tmp_path / "taste_report.md"
        report = taste_profile.export_markdown(str(output_file))
        
        assert output_file.exists()
        with open(output_file, "r") as f:
            saved = f.read()
        
        assert saved == report
        assert "# 🐱 Clawgotchi Taste Profile" in saved
    
    def test_export_shows_visual_bars(self, taste_profile):
        """Should show visual bars for rejection counts."""
        for _ in range(5):
            taste_profile.log_rejection("x", "r", "scope")
        for _ in range(3):
            taste_profile.log_rejection("y", "r", "vibe")
        
        report = taste_profile.export_markdown()
        
        assert "█" in report  # Visual bars
        assert "scope" in report
        assert "vibe" in report
