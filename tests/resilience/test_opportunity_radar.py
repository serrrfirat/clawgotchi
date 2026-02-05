"""
Tests for Opportunity Radar - Moltbook opportunity detection
"""
import json
import pytest
from clawgotchi.resilience.opportunity_radar import (
    OpportunityType,
    OpportunitySignal,
    OpportunityRadar,
    quick_scan
)


class TestOpportunityType:
    """Test OpportunityType enum values"""
    
    def test_all_types_exist(self):
        """Verify all expected opportunity types are defined"""
        types = list(OpportunityType)
        assert len(types) == 5
        assert OpportunityType.TOOL_REQUEST in types
        assert OpportunityType.PROBLEM_COMPLAINT in types
        assert OpportunityType.FEATURE_REQUEST in types
        assert OpportunityType.INTEGRATION_NEED in types
        assert OpportunityType.AUTOMATION_GAP in types
    
    def test_type_string_values(self):
        """Verify type string values are correct"""
        assert OpportunityType.TOOL_REQUEST.value == "tool_request"
        assert OpportunityType.PROBLEM_COMPLAINT.value == "problem_complaint"
        assert OpportunityType.FEATURE_REQUEST.value == "feature_request"
        assert OpportunityType.INTEGRATION_NEED.value == "integration_need"
        assert OpportunityType.AUTOMATION_GAP.value == "automation_gap"


class TestOpportunitySignal:
    """Test OpportunitySignal dataclass"""
    
    def test_create_signal(self):
        """Test creating an opportunity signal"""
        signal = OpportunitySignal(
            post_id="test-123",
            post_title="I wish there was a tool for X",
            opportunity_type=OpportunityType.TOOL_REQUEST,
            confidence=0.75,
            keywords=["wish there was"],
            content_snippet="I really wish..."
        )
        
        assert signal.post_id == "test-123"
        assert signal.opportunity_type == OpportunityType.TOOL_REQUEST
        assert signal.confidence == 0.75
        assert "wish there was" in signal.keywords
    
    def test_signal_to_dict(self):
        """Test serialization to dictionary"""
        signal = OpportunitySignal(
            post_id="test-456",
            post_title="Tired of manual work",
            opportunity_type=OpportunityType.PROBLEM_COMPLAINT,
            confidence=0.8,
            keywords=["tired of", "manual"],
            content_snippet="This is frustrating..."
        )
        
        data = signal.to_dict()
        
        assert data["post_id"] == "test-456"
        assert data["opportunity_type"] == "problem_complaint"
        assert data["confidence"] == 0.8
        assert data["keywords"] == ["tired of", "manual"]
    
    def test_signal_from_dict(self):
        """Test deserialization from dictionary"""
        data = {
            "post_id": "test-789",
            "post_title": "Would be cool to automate Y",
            "opportunity_type": "automation_gap",
            "confidence": 0.65,
            "keywords": ["automate"],
            "content_snippet": "I wish...",
            "source_url": "https://example.com/post"
        }
        
        signal = OpportunitySignal.from_dict(data)
        
        assert signal.post_id == "test-789"
        assert signal.opportunity_type == OpportunityType.AUTOMATION_GAP
        assert signal.confidence == 0.65
        assert signal.source_url == "https://example.com/post"
    
    def test_roundtrip_serialization(self):
        """Test that to_dict and from_dict are inverses"""
        original = OpportunitySignal(
            post_id="roundtrip-123",
            post_title="Integration needed",
            opportunity_type=OpportunityType.INTEGRATION_NEED,
            confidence=0.9,
            keywords=["integrate", "connect"],
            content_snippet="Need X to connect with Y"
        )
        
        restored = OpportunitySignal.from_dict(original.to_dict())
        
        assert restored.post_id == original.post_id
        assert restored.post_title == original.post_title
        assert restored.opportunity_type == original.opportunity_type
        assert restored.confidence == original.confidence
        assert restored.keywords == original.keywords


class TestOpportunityRadar:
    """Test OpportunityRadar class"""
    
    def setup_method(self):
        """Set up fresh radar for each test"""
        self.radar = OpportunityRadar()
    
    def test_scan_empty_feed(self):
        """Test scanning an empty feed returns empty list"""
        signals = self.radar.scan_feed([])
        assert signals == []
    
    def test_scan_no_opportunities(self):
        """Test scanning posts with no opportunity keywords"""
        posts = [
            {"id": "1", "title": "Hello World", "content": "Just saying hi"},
            {"id": "2", "title": "Nice day", "content": "The weather is good"}
        ]
        signals = self.radar.scan_feed(posts)
        assert signals == []
    
    def test_tool_request_detection(self):
        """Test detecting tool requests"""
        posts = [
            {
                "id": "post-1",
                "title": "I wish there was a tool for JSON escaping",
                "content": "Does anyone know of a tool?",
                "url": "https://example.com/1"
            }
        ]
        signals = self.radar.scan_feed(posts)

        assert len(signals) >= 1
        tool_signals = [s for s in signals if s.opportunity_type == OpportunityType.TOOL_REQUEST]
        assert len(tool_signals) >= 1
        assert tool_signals[0].confidence >= 0.3
    
    def test_problem_complaint_detection(self):
        """Test detecting problem complaints"""
        posts = [
            {
                "id": "post-2",
                "title": "This is so annoying",
                "content": "I'm tired of doing this manually every day"
            }
        ]
        signals = self.radar.scan_feed(posts)
        
        assert len(signals) >= 1
        complaint_signals = [s for s in signals if s.opportunity_type == OpportunityType.PROBLEM_COMPLAINT]
        assert len(complaint_signals) >= 1
    
    def test_automation_gap_detection(self):
        """Test detecting automation gaps"""
        posts = [
            {
                "id": "post-3",
                "title": "Would be nice to automate this",
                "content": "I keep having to run this script manually"
            }
        ]
        signals = self.radar.scan_feed(posts)
        
        assert len(signals) >= 1
        auto_signals = [s for s in signals if s.opportunity_type == OpportunityType.AUTOMATION_GAP]
        assert len(auto_signals) >= 1
    
    def test_multiple_opportunities_in_one_post(self):
        """Test detecting multiple opportunity types in single post"""
        posts = [
            {
                "id": "post-multi",
                "title": "I wish there was a tool - this is so annoying and should be automated",
                "content": "Tired of doing this manually"
            }
        ]
        signals = self.radar.scan_feed(posts)
        
        # Should detect at least 2 types
        assert len(signals) >= 2
    
    def test_title_match_boosts_confidence(self):
        """Test that keyword matches in title boost confidence"""
        radar1 = OpportunityRadar()
        radar2 = OpportunityRadar()
        
        # Match in title
        posts_title = [{"id": "1", "title": "I wish there was a tool", "content": "..."}]
        signals_title = radar1.scan_feed(posts_title)
        
        # Match only in content
        posts_content = [{"id": "2", "title": "Something else", "content": "I wish there was a tool here"}]
        signals_content = radar2.scan_feed(posts_content)
        
        if signals_title and signals_content:
            assert signals_title[0].confidence >= signals_content[0].confidence
    
    def test_score_opportunity_basic(self):
        """Test basic opportunity scoring"""
        signal = OpportunitySignal(
            post_id="score-test",
            post_title="Test",
            opportunity_type=OpportunityType.TOOL_REQUEST,
            confidence=0.5,
            keywords=["wish there was"],
            content_snippet="..."
        )
        
        score = self.radar.score_opportunity(signal)
        
        assert 0.0 <= score <= 1.0
    
    def test_tool_request_high_type_weight(self):
        """Test that TOOL_REQUEST gets higher type weight"""
        tool_signal = OpportunitySignal(
            post_id="1",
            post_title="Test",
            opportunity_type=OpportunityType.TOOL_REQUEST,
            confidence=0.5,
            keywords=["test"],
            content_snippet="..."
        )
        
        feature_signal = OpportunitySignal(
            post_id="2",
            post_title="Test",
            opportunity_type=OpportunityType.FEATURE_REQUEST,
            confidence=0.5,
            keywords=["test"],
            content_snippet="..."
        )
        
        tool_score = self.radar.score_opportunity(tool_signal)
        feature_score = self.radar.score_opportunity(feature_signal)
        
        assert tool_score >= feature_score
    
    def test_get_top_opportunities_limits_results(self):
        """Test that get_top_opportunities respects limit"""
        # Create multiple signals
        for i in range(10):
            self.radar._detected_opportunities.append(OpportunitySignal(
                post_id=f"post-{i}",
                post_title=f"Test {i}",
                opportunity_type=OpportunityType.TOOL_REQUEST,
                confidence=0.3 + (i * 0.07),
                keywords=["test"],
                content_snippet="..."
            ))
        
        top_3 = self.radar.get_top_opportunities(limit=3)
        top_5 = self.radar.get_top_opportunities(limit=5)
        
        assert len(top_3) == 3
        assert len(top_5) == 5
    
    def test_get_top_opportunities_sorted_by_score(self):
        """Test that top opportunities are sorted by score descending"""
        # Create signals with known confidence scores
        for i, conf in enumerate([0.9, 0.3, 0.7, 0.5, 0.1]):
            self.radar._detected_opportunities.append(OpportunitySignal(
                post_id=f"post-{i}",
                post_title=f"Test {i}",
                opportunity_type=OpportunityType.TOOL_REQUEST,
                confidence=conf,
                keywords=["test"],
                content_snippet="..."
            ))
        
        top = self.radar.get_top_opportunities(limit=5)
        
        # Verify descending order
        scores = [self.radar.score_opportunity(s) for s in top]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]
    
    def test_save_and_load_opportunities(self, tmp_path):
        """Test saving and loading opportunities"""
        signals = [
            OpportunitySignal(
                post_id="save-1",
                post_title="Save Test 1",
                opportunity_type=OpportunityType.AUTOMATION_GAP,
                confidence=0.8,
                keywords=["automate"],
                content_snippet="..."
            ),
            OpportunitySignal(
                post_id="save-2",
                post_title="Save Test 2",
                opportunity_type=OpportunityType.PROBLEM_COMPLAINT,
                confidence=0.6,
                keywords=["annoying"],
                content_snippet="..."
            )
        ]
        
        # Save
        self.radar._detected_opportunities = signals
        storage = OpportunityRadar(storage_path=str(tmp_path))
        filepath = storage.save_opportunities(signals)
        
        assert filepath != ""
        assert tmp_path.joinpath(filepath.split("/")[-1]).exists()
        
        # Load
        loaded = storage.load_opportunities(filepath)
        
        assert len(loaded) == 2
        assert loaded[0].post_id == "save-1"
        assert loaded[1].post_id == "save-2"
    
    def test_get_stats_empty(self):
        """Test getting stats with no opportunities"""
        stats = self.radar.get_stats()
        
        assert stats["total"] == 0
        assert stats["by_type"] == {}
    
    def test_get_stats_with_data(self):
        """Test getting stats with opportunities"""
        # Add some signals
        self.radar._detected_opportunities = [
            OpportunitySignal(
                post_id="1",
                post_title="Test 1",
                opportunity_type=OpportunityType.TOOL_REQUEST,
                confidence=0.5,
                keywords=["test"],
                content_snippet="..."
            ),
            OpportunitySignal(
                post_id="2",
                post_title="Test 2",
                opportunity_type=OpportunityType.TOOL_REQUEST,
                confidence=0.6,
                keywords=["test"],
                content_snippet="..."
            ),
            OpportunitySignal(
                post_id="3",
                post_title="Test 3",
                opportunity_type=OpportunityType.AUTOMATION_GAP,
                confidence=0.7,
                keywords=["test"],
                content_snippet="..."
            )
        ]
        
        stats = self.radar.get_stats()
        
        assert stats["total"] == 3
        assert stats["by_type"]["tool_request"] == 2
        assert stats["by_type"]["automation_gap"] == 1


class TestQuickScan:
    """Test convenience function"""
    
    def test_quick_scan_returns_top_opportunities(self):
        """Test quick_scan returns limited results"""
        posts = [
            {"id": "1", "title": "I wish there was X", "content": "..."},
            {"id": "2", "title": "Tired of Y", "content": "..."},
            {"id": "3", "title": "Would be cool to automate Z", "content": "..."},
            {"id": "4", "title": "Need integration for A", "content": "..."},
            {"id": "5", "title": "Feature request: B", "content": "..."}
        ]
        
        results = quick_scan(posts, limit=3)
        
        assert len(results) <= 3
    
    def test_quick_scan_handles_empty(self):
        """Test quick_scan with empty feed"""
        results = quick_scan([])
        assert results == []


class TestIntegration:
    """Integration tests with realistic Moltbook data"""
    
    def test_scan_realistic_feed(self):
        """Test scanning with realistic Moltbook-style posts"""
        posts = [
            {
                "id": "real-1",
                "title": "JSON escaping is a nightmare",
                "content": "Every time I post to Moltbook with an apostrophe, it breaks. I wish there was a tool for this.",
                "url": "https://moltbook.com/p/real-1"
            },
            {
                "id": "real-2",
                "title": "Built a new spectrogram tool",
                "content": "Just released songsee for audio visualization. Check it out!"
            },
            {
                "id": "real-3",
                "title": "Agents keep shilling - security audit time",
                "content": "Tired of seeing the same low-entropy shills everywhere. This is so annoying."
            },
            {
                "id": "real-4",
                "title": "Would be nice if X integrated with Y",
                "content": "Has anyone connected their agent to Moltbook API automatically?"
            }
        ]
        
        radar = OpportunityRadar()
        signals = radar.scan_feed(posts)
        
        # Should detect:
        # real-1: TOOL_REQUEST (wish there was) + PROBLEM_COMPLAINT (nightmare)
        # real-3: PROBLEM_COMPLAINT (tired of, annoying)
        # real-4: INTEGRATION_NEED (integrated) + FEATURE_REQUEST (would be nice)
        
        assert len(signals) >= 3
        
        # Check stats
        stats = radar.get_stats()
        assert stats["total"] >= 3
    
    def test_opportunity_radar_complements_memory_systems(self):
        """Verify radar can work with memory triage patterns"""
        posts = [
            {
                "id": "mem-1",
                "title": "IMPORTANT: Context compression causing amnesia",
                "content": "Critical: Agent keeps forgetting what we discussed. This keeps happening."
            }
        ]
        
        radar = OpportunityRadar()
        signals = radar.scan_feed(posts)
        
        # This would be detected as both PROBLEM_COMPLAINT and AUTOMATION_GAP
        if signals:
            stats = radar.get_stats()
            assert stats["total"] >= 1
