"""Test suite for Content Relevance Scorer."""

import pytest
from datetime import datetime
from utils.content_relevance_scorer import ContentRelevanceScorer, RelevanceConfig, ScoredChunk


def test_scorer_initialization():
    """Test that scorer initializes with default config."""
    scorer = ContentRelevanceScorer()
    assert scorer.config is not None
    assert scorer.config.exact_match_weight == 2.0
    assert scorer.config.partial_match_weight == 1.0
    assert scorer.config.recency_weight == 0.5
    assert scorer.config.recency_days == 7


def test_scorer_custom_config():
    """Test scorer with custom configuration."""
    config = RelevanceConfig(
        exact_match_weight=3.0,
        partial_match_weight=1.5,
        recency_weight=1.0,
        recency_days=14
    )
    scorer = ContentRelevanceScorer(config)
    assert scorer.config.exact_match_weight == 3.0
    assert scorer.config.recency_days == 14


def test_score_topic_matches():
    """Test scoring based on topic matching."""
    scorer = ContentRelevanceScorer()
    
    text = "I love working with Python and AI agents"
    topics = ["python", "ai"]
    
    score = scorer.score(text, topics)
    assert score.total_score > 0
    assert score.exact_matches >= 2
    assert score.partial_matches >= 0


def test_case_insensitive_matching():
    """Test that matching is case insensitive."""
    scorer = ContentRelevanceScorer()
    
    text = "PYTHON is great"
    topics = ["python"]
    
    score = scorer.score(text, topics)
    assert score.exact_matches == 1


def test_no_matching_topics():
    """Test score when no topics match."""
    scorer = ContentRelevanceScorer()
    
    text = "Random text about weather"
    topics = ["python", "ai"]
    
    score = scorer.score(text, topics)
    assert score.total_score == 0
    assert score.exact_matches == 0
    assert score.partial_matches == 0


def test_relevance_threshold():
    """Test relevance threshold filtering."""
    scorer = ContentRelevanceScorer()
    
    # High relevance content with weighted topics
    high_text = "Python AI agents are transforming automation"
    high_topics = {"python": 3.0, "ai": 3.0}  # Higher weights for testing
    assert scorer.is_relevant(high_text, high_topics, threshold=5.0) is True
    
    # Low relevance content
    low_text = "Weather is sunny today"
    low_topics = ["python", "ai"]
    assert scorer.is_relevant(low_text, low_topics, threshold=1.0) is False


def test_multi_topic_scoring():
    """Test scoring with multiple topics of varying importance."""
    scorer = ContentRelevanceScorer()
    
    text = "The Python framework uses AI for natural language processing"
    topics = {
        "python": 2.0,       # High priority
        "ai": 1.5,          # Medium priority
        "nlp": 1.0          # Lower priority
    }
    
    score = scorer.score(text, topics)
    assert score.total_score > 0
    assert score.breakdown["python"] > 0


def test_chunk_scoring():
    """Test chunk-level scoring for large documents."""
    scorer = ContentRelevanceScorer()
    
    chunks = [
        "First section about weather",
        "Python AI integration here",
        "More content unrelated"
    ]
    topics = ["python", "ai"]
    
    results = scorer.score_chunks(chunks, topics)
    assert len(results) == 3
    # Second chunk should have highest score
    assert results[1].total_score > results[0].total_score
    assert results[1].total_score > results[2].total_score


def test_get_relevant_chunks():
    """Test extracting only relevant chunks above threshold."""
    scorer = ContentRelevanceScorer()
    
    chunks = [
        "Weather is sunny",           # Not relevant
        "Python AI here",             # Relevant
        "More weather stuff",         # Not relevant
        "Python automation wins"      # Relevant
    ]
    topics = ["python", "ai"]
    
    relevant = scorer.get_relevant_chunks(chunks, topics, threshold=1.0)
    assert len(relevant) == 2


def test_keyword_extraction():
    """Test automatic keyword extraction."""
    scorer = ContentRelevanceScorer()
    
    text = """
    Python is a programming language used for AI and machine learning.
    Many developers use Python for data science and automation.
    """
    
    keywords = scorer.extract_keywords(text, max_keywords=5)
    assert len(keywords) <= 5
    assert "python" in keywords or "Python" in keywords


def test_topic_ranking():
    """Test ranking topics by relevance to content."""
    scorer = ContentRelevanceScorer()
    
    text = "Python AI automation tools"
    candidate_topics = ["python", "weather", "ai", "cooking", "automation"]
    
    ranked = scorer.rank_topics(text, candidate_topics)
    assert len(ranked) == len(candidate_topics)
    # Python, AI, and automation should be top
    assert ranked[0][0] in ["python", "ai", "automation"]
    # Weather and cooking should be bottom
    assert ranked[-1][0] in ["weather", "cooking"]


def test_relevance_summary():
    """Test getting a summary of content relevance."""
    scorer = ContentRelevanceScorer()
    
    text = "Advanced Python AI automation with neural networks"
    topics = ["python", "ai"]
    
    summary = scorer.get_relevance_summary(text, topics)
    assert "score" in summary
    assert "is_relevant" in summary
    assert "matches" in summary


def test_empty_content():
    """Test handling of empty content."""
    scorer = ContentRelevanceScorer()
    
    score = scorer.score("", ["python"])
    assert score.total_score == 0
    
    score = scorer.score("Some text", [])
    assert score.total_score == 0


def test_empty_topics():
    """Test handling when topics is empty."""
    scorer = ContentRelevanceScorer()
    
    # Should not raise an error
    score = scorer.score("Python AI text", [])
    assert score.total_score == 0


def test_special_characters():
    """Test handling of special characters and formatting."""
    scorer = ContentRelevanceScorer()
    
    text = "Python! @#$% AI &*() automation"
    topics = ["python", "ai"]
    
    score = scorer.score(text, topics)
    # Should still find matches despite special characters
    assert score.exact_matches >= 2


def test_score_breakdown_structure():
    """Test that score breakdown has correct structure."""
    scorer = ContentRelevanceScorer()
    
    text = "Python and AI are great"
    topics = {"python": 2.0, "ai": 1.5}
    
    score = scorer.score(text, topics)
    assert "python" in score.breakdown
    assert "ai" in score.breakdown
    assert isinstance(score.breakdown["python"], float)


def test_url_scoring():
    """Test scoring URLs for relevance."""
    scorer = ContentRelevanceScorer()
    
    url = "https://github.com/python/ai-agent"
    topics = ["python", "ai"]
    
    score = scorer.score(url, topics)
    # URL should be scored based on path/segments
    assert score.total_score >= 0


def test_whitespace_handling():
    """Test that whitespace is handled properly."""
    scorer = ContentRelevanceScorer()
    
    text = "Python   AI    automation"  # Multiple spaces
    topics = ["python", "ai"]
    
    score = scorer.score(text, topics)
    assert score.exact_matches >= 2
