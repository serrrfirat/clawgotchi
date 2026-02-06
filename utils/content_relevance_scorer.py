"""Content Relevance Scorer.

A flexible utility to score content relevance against topics/keywords
for filtering and prioritization. Powers context filtering and
intelligence briefing systems.

Inspired by RyanAssistant's insight: "filtering quality matters more
than generation quality" - Moltbook 2026-02-06
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import re
from datetime import datetime, timedelta


@dataclass
class RelevanceConfig:
    """Configuration for relevance scoring behavior."""
    exact_match_weight: float = 2.0
    partial_match_weight: float = 1.0
    recency_weight: float = 0.5
    recency_days: int = 7
    case_sensitive: bool = False
    min_word_length: int = 2
    use_stemming: bool = False


@dataclass
class ScoredChunk:
    """Result of scoring a chunk of content."""
    text: str
    total_score: float
    exact_matches: int
    partial_matches: int
    breakdown: Dict[str, float]
    is_relevant: bool = field(default=False)


class ContentRelevanceScorer:
    """Scores content relevance against defined topics/keywords."""
    
    def __init__(self, config: Optional[RelevanceConfig] = None):
        """Initialize scorer with optional custom config.
        
        Args:
            config: Optional RelevanceConfig. Creates default if not provided.
        """
        self.config = config or RelevanceConfig()
    
    def score(self, content: str, topics: Dict[str, float]) -> ScoredChunk:
        """Score content against topic weights.
        
        Args:
            content: Text content to score
            topics: Dict mapping topic keywords to their weights, or list of topics (default weight 1.0)
            
        Returns:
            ScoredChunk with total score and breakdown
        """
        if not content or not topics:
            return ScoredChunk(
                text=content or "",
                total_score=0.0,
                exact_matches=0,
                partial_matches=0,
                breakdown={},
                is_relevant=False
            )
        
        # Support both list and dict inputs
        if isinstance(topics, list):
            topics = {t: 1.0 for t in topics}
        
        # Normalize content
        normalized = self._normalize(content)
        words = self._tokenize(normalized)
        
        breakdown = {}
        exact_matches = 0
        partial_matches = 0
        
        for topic, weight in topics.items():
            norm_topic = self._normalize(topic)
            topic_score = 0.0
            topic_exact = 0
            topic_partial = 0
            
            # Exact match (whole word)
            if norm_topic in words:
                topic_score += weight * self.config.exact_match_weight
                topic_exact += 1
                exact_matches += 1
            
            # Partial match (contained in word)
            for word in words:
                if len(word) >= self.config.min_word_length:
                    if norm_topic in word and norm_topic != word:
                        topic_score += weight * self.config.partial_match_weight
                        topic_partial += 1
                        partial_matches += 1
            
            if topic_score > 0:
                breakdown[topic] = topic_score
        
        total_score = sum(breakdown.values())
        
        return ScoredChunk(
            text=content,
            total_score=round(total_score, 2),
            exact_matches=exact_matches,
            partial_matches=partial_matches,
            breakdown=breakdown,
            is_relevant=total_score > 0
        )
    
    def score_chunks(
        self, 
        chunks: List[str], 
        topics: Dict[str, float]
    ) -> List[ScoredChunk]:
        """Score multiple chunks of content.
        
        Args:
            chunks: List of text chunks
            topics: Dict mapping topic keywords to their weights
            
        Returns:
            List of ScoredChunks in same order as input
        """
        return [self.score(chunk, topics) for chunk in chunks]
    
    def is_relevant(
        self, 
        content: str, 
        topics: Dict[str, float],
        threshold: float = 1.0
    ) -> bool:
        """Check if content meets relevance threshold.
        
        Args:
            content: Text to check
            topics: Topic weights
            threshold: Minimum score to be considered relevant
            
        Returns:
            True if content is relevant, False otherwise
        """
        score = self.score(content, topics)
        return score.total_score >= threshold
    
    def get_relevant_chunks(
        self,
        chunks: List[str],
        topics: Dict[str, float],
        threshold: float = 1.0
    ) -> List[ScoredChunk]:
        """Extract chunks that pass the relevance threshold.
        
        Args:
            chunks: List of text chunks
            topics: Topic weights
            threshold: Minimum score to be considered relevant
            
        Returns:
            List of relevant ScoredChunks
        """
        scored = self.score_chunks(chunks, topics)
        return [chunk for chunk in scored if chunk.is_relevant]
    
    def rank_topics(
        self, 
        content: str, 
        candidate_topics: List[str]
    ) -> List[Tuple[str, float]]:
        """Rank candidate topics by their relevance to content.
        
        Args:
            content: Text to analyze
            candidate_topics: List of topics to rank
            
        Returns:
            List of (topic, score) tuples sorted by score descending
        """
        # Create equal weights for all candidates
        weights = {t: 1.0 for t in candidate_topics}
        
        scored = self.score(content, weights)
        
        # Sort by individual topic scores
        ranked = sorted(
            scored.breakdown.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Add zeros for topics with no matches
        matched_topics = set(scored.breakdown.keys())
        for topic in candidate_topics:
            norm = self._normalize(topic)
            if norm not in matched_topics:
                ranked.append((topic, 0.0))
        
        return ranked
    
    def extract_keywords(
        self, 
        content: str, 
        max_keywords: int = 10
    ) -> List[str]:
        """Extract potential keywords from content.
        
        Simple frequency-based extraction. For production, consider
        using NLP libraries like spaCy or nltk.
        
        Args:
            content: Text to extract from
            max_keywords: Maximum number of keywords to return
            
        Returns:
            List of extracted keywords (lowercase)
        """
        if not content:
            return []
        
        normalized = self._normalize(content)
        words = self._tokenize(normalized)
        
        # Filter short words and common stopwords
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'and', 'but', 'or', 'nor', 'so', 'yet', 'both', 'either',
            'neither', 'not', 'only', 'own', 'same', 'than', 'too',
            'very', 'just', 'also', 'now', 'this', 'that', 'these',
            'those', 'what', 'which', 'who', 'whom', 'whose', 'when',
            'where', 'why', 'how', 'all', 'each', 'every', 'some', 'any'
        }
        
        filtered = [
            w for w in words 
            if len(w) >= self.config.min_word_length 
            and w not in stopwords
        ]
        
        # Count frequencies
        freq = {}
        for word in filtered:
            freq[word] = freq.get(word, 0) + 1
        
        # Sort by frequency and return top N
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        
        return [word for word, _ in sorted_words[:max_keywords]]
    
    def get_relevance_summary(
        self, 
        content: str, 
        topics: Dict[str, float]
    ) -> Dict:
        """Get a summary of content relevance.
        
        Args:
            content: Text to analyze
            topics: Topic weights
            
        Returns:
            Dict with score, is_relevant, and match details
        """
        scored = self.score(content, topics)
        
        return {
            "score": scored.total_score,
            "is_relevant": scored.is_relevant,
            "matches": {
                "exact": scored.exact_matches,
                "partial": scored.partial_matches,
                "breakdown": scored.breakdown
            }
        }
    
    def _normalize(self, text: str) -> str:
        """Normalize text for consistent matching."""
        if self.config.case_sensitive:
            return text.lower()
        return text.lower()
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Remove punctuation and split on whitespace
        cleaned = re.sub(r'[^\w\s]', ' ', text)
        tokens = cleaned.split()
        return tokens


# Convenience functions

def score_content(
    content: str, 
    topics: Dict[str, float],
    **kwargs
) -> ScoredChunk:
    """Quick function to score content with default config.
    
    Args:
        content: Text to score
        topics: Topic weights
        **kwargs: Optional config overrides
        
    Returns:
        ScoredChunk result
    """
    if kwargs:
        config = RelevanceConfig(**kwargs)
        scorer = ContentRelevanceScorer(config)
    else:
        scorer = ContentRelevanceScorer()
    
    return scorer.score(content, topics)


def filter_relevant(
    contents: List[str],
    topics: Dict[str, float],
    threshold: float = 1.0
) -> List[Tuple[str, float]]:
    """Filter list of contents by relevance.
    
    Args:
        contents: List of texts to filter
        topics: Topic weights
        threshold: Minimum score to keep
        
    Returns:
        List of (content, score) tuples for relevant items
    """
    scorer = ContentRelevanceScorer()
    results = []
    
    for content in contents:
        scored = scorer.score(content, topics)
        if scored.total_score >= threshold:
            results.append((content, scored.total_score))
    
    return results
