"""
Test suite for Opportunity Radar Module
Detects buildable opportunities from Moltbook feed and community signals.
"""

import pytest
import json
from datetime import datetime


def get_opportunity_types():
    """Returns the enum of opportunity types."""
    from opportunity_radar import OpportunityType
    return OpportunityType


class TestOpportunityType:
    """Tests for OpportunityType enum."""

    def test_opportunity_types_exist(self):
        """Verify all opportunity types are defined."""
        types = get_opportunity_types()
        expected = [
            'TOOL_REQUEST',      # "I need a tool to do X"
            'PROBLEM_COMPLAINT', # "X is broken/broken/doesn't work"
            'FEATURE_REQUEST',   # "It would be great if X had Y"
            'INTEGRATION_NEED',  # "X should work with Y"
            'AUTOMATION_GAP',    # "I have to do X manually"
        ]
        for expected_type in expected:
            assert hasattr(types, expected_type), f"Missing opportunity type: {expected_type}"


class TestConfidenceScoring:
    """Tests for confidence scoring system."""

    def test_confidence_zero_for_neutral(self):
        """Neutral content should score near zero."""
        from opportunity_radar import calculate_confidence
        result = calculate_confidence(
            title="Just had lunch",
            content="The sandwich was okay.",
            keywords=[]
        )
        assert result >= 0.0 and result <= 0.2

    def test_confidence_high_for_tool_request(self):
        """Tool requests should score high."""
        from opportunity_radar import calculate_confidence
        result = calculate_confidence(
            title="I need a tool to automate my Twitter posts",
            content="Does anyone know a tool that can schedule tweets automatically?",
            keywords=["tool", "automate", "schedule"]
        )
        assert result >= 0.7

    def test_confidence_high_for_problem_complaint(self):
        """Problem complaints should score high."""
        from opportunity_radar import calculate_confidence
        result = calculate_confidence(
            title="This is broken!",
            content="My agent keeps crashing when I try to post to Moltbook.",
            keywords=["broken", "crashing", "fix"]
        )
        assert result >= 0.7

    def test_title_match_boosts_confidence(self):
        """Title matches should boost confidence."""
        from opportunity_radar import calculate_confidence
        with_title = calculate_confidence(
            title="FEATURE REQUEST: Dark mode",
            content="Please add dark mode.",
            keywords=["dark", "mode"]
        )
        without_title = calculate_confidence(
            title="Hello everyone",
            content="Please add dark mode.",
            keywords=["dark", "mode"]
        )
        assert with_title > without_title


class TestKeywordExtraction:
    """Tests for keyword extraction patterns."""

    def test_tool_keywords(self):
        """Tool requests should have specific keywords."""
        from opportunity_radar import extract_keywords
        keywords = extract_keywords("I need a tool to automate my calendar")
        assert any(kw in keywords for kw in ["tool", "automate", "calendar"])

    def test_problem_keywords(self):
        """Problem complaints should have specific keywords."""
        from opportunity_radar import extract_keywords
        keywords = extract_keywords("This is broken and doesn't work")
        assert any(kw in keywords for kw in ["broken", "fix", "error", "work"])

    def test_feature_keywords(self):
        """Feature requests should have specific keywords."""
        from opportunity_radar import extract_keywords
        keywords = extract_keywords("Would be great if we had dark mode")
        assert any(kw in keywords for kw in ["feature", "request", "add", "mode"])


class TestOpportunityDetection:
    """Tests for full opportunity detection pipeline."""

    def test_detect_tool_request(self):
        """Should detect tool requests with high confidence."""
        from opportunity_radar import detect_opportunity
        opportunity = detect_opportunity(
            title="Looking for a Moltbook posting tool",
            content="I need something to automate my posts to Moltbook.",
            author="test_user"
        )
        assert opportunity is not None
        assert opportunity['type'] == 'TOOL_REQUEST'
        assert opportunity['confidence'] >= 0.7

    def test_detect_problem_complaint(self):
        """Should detect problem complaints."""
        from opportunity_radar import detect_opportunity
        opportunity = detect_opportunity(
            title="Help! My agent is broken",
            content="It keeps failing when I try to use the CLI.",
            author="test_user"
        )
        assert opportunity is not None
        assert opportunity['type'] == 'PROBLEM_COMPLAINT'
        assert opportunity['confidence'] >= 0.6

    def test_detect_integration_need(self):
        """Should detect integration needs."""
        from opportunity_radar import detect_opportunity
        opportunity = detect_opportunity(
            title="Can Moltbook integrate with Slack?",
            content="I want my posts to go to Slack automatically.",
            author="test_user"
        )
        assert opportunity is not None
        assert opportunity['type'] == 'INTEGRATION_NEED'

    def test_detect_automation_gap(self):
        """Should detect automation gaps."""
        from opportunity_radar import detect_opportunity
        opportunity = detect_opportunity(
            title="I have to manually post every morning",
            content="Wish there was a way to automate this.",
            author="test_user"
        )
        assert opportunity is not None
        assert opportunity['type'] == 'AUTOMATION_GAP'


class TestGetTopOpportunities:
    """Tests for ranking and filtering opportunities."""

    def test_ranking_highest_confidence_first(self):
        """Should return highest confidence opportunities first."""
        from opportunity_radar import get_top_opportunities
        opportunities = [
            {'type': 'TOOL_REQUEST', 'confidence': 0.3, 'title': 'Low confidence'},
            {'type': 'PROBLEM_COMPLAINT', 'confidence': 0.9, 'title': 'High confidence'},
            {'type': 'FEATURE_REQUEST', 'confidence': 0.7, 'title': 'Medium confidence'},
        ]
        ranked = get_top_opportunities(opportunities, limit=2)
        assert len(ranked) == 2
        assert ranked[0]['confidence'] >= ranked[1]['confidence']

    def test_empty_list(self):
        """Should handle empty opportunity list."""
        from opportunity_radar import get_top_opportunities
        result = get_top_opportunities([])
        assert result == []

    def test_limit_results(self):
        """Should respect limit parameter."""
        from opportunity_radar import get_top_opportunities
        opportunities = [
            {'type': 'TOOL_REQUEST', 'confidence': 0.9, 'title': f'Opportunity {i}'}
            for i in range(10)
        ]
        result = get_top_opportunities(opportunities, limit=5)
        assert len(result) == 5
